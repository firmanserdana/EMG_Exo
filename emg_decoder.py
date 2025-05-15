#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EMG Decoding Module
Performs gesture and movement classification from EMG signals using machine learning.
"""

import numpy as np
import time
import os
import pickle
from datetime import datetime
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import confusion_matrix, accuracy_score, classification_report
import joblib
import h5py
import pandas as pd

from ini import DECODING, DOF_CONFIG, MODEL_DIR, logger


class EMGDecoder:
    """Class for decoding EMG signals into hand/finger movements."""
    
    def __init__(self):
        """Initialize the EMG decoder."""
        self.classifiers = {}
        self.scalers = {}
        self.feature_names = DECODING["features"]
        self.gesture_names = self._get_gesture_names()
        self.training_ratio = DECODING["training_ratio"]
        self.cv_folds = DECODING["cv_folds"]
        self.normalize = DECODING["normalize"]
        self.model_dir = MODEL_DIR
        self.trained = False
        
        # Initialize classifiers
        self._create_classifiers()
        
        logger.info("EMG decoder initialized")
        
    def _get_gesture_names(self):
        """Generate gesture names from DoF configuration.
        
        Returns:
            list: List of gesture names
        """
        gestures = []
        
        # Add finger movements based on DOF_CONFIG
        for finger in ["thumb", "index", "middle"]:
            for movement in DOF_CONFIG[finger]:
                gestures.append(f"{finger}_{movement}")
        
        # Add ring and little finger movements
        for movement in DOF_CONFIG["ring_little"]:
            gestures.append(f"ring_little_{movement}")
        
        # Add thumb abduction if configured
        if DOF_CONFIG["thumb_abduction"]:
            gestures.append("thumb_abduction")
            
        # Add some combined gestures (common hand postures)
        gestures.extend([
            "power_grip", 
            "precision_grip", 
            "rest",
            "open_hand"
        ])
        
        return gestures
        
    def _create_classifiers(self):
        """Create and initialize the configured classifiers."""
        if "kNN" in DECODING["classifiers"]:
            self.classifiers["kNN"] = KNeighborsClassifier(
                n_neighbors=5,
                weights='distance',
                algorithm='auto',
                leaf_size=30, 
                p=2,  # Euclidean distance
                metric='minkowski'
            )
            self.scalers["kNN"] = StandardScaler()
            
        if "MLP" in DECODING["classifiers"]:
            self.classifiers["MLP"] = MLPClassifier(
                hidden_layer_sizes=(100, 100),
                activation='relu',
                solver='adam',
                alpha=0.0001,
                batch_size='auto',
                learning_rate='adaptive',
                max_iter=500,
                early_stopping=True,
                validation_fraction=0.1,
                random_state=42
            )
            self.scalers["MLP"] = StandardScaler()
    
    def extract_classification_features(self, features_dict):
        """Extract classification features from preprocessed EMG data.
        
        Args:
            features_dict (dict): Dictionary of feature values from EMGProcessor
            
        Returns:
            numpy.ndarray: Feature vector for classification
        """
        if not features_dict:
            return np.array([])
        
        feature_vector = []
        
        # Collect requested features
        for feature in self.feature_names:
            if feature.lower() == "rms" and "rms" in features_dict:
                feature_vector.extend(features_dict["rms"])
            elif feature.lower() == "mav" and "mav" in features_dict:
                feature_vector.extend(features_dict["mav"])
            elif feature.lower() == "wl" and "wl" in features_dict:
                feature_vector.extend(features_dict["wl"])
            elif feature.lower() == "zc" and "zc" in features_dict:
                feature_vector.extend(features_dict["zc"])
            elif feature.lower() == "ssc" and "ssc" in features_dict:
                feature_vector.extend(features_dict["ssc"])
            elif feature.lower() == "ar" and "ar" in features_dict:
                # AR coefficients are 2D, flatten them
                ar_coeffs = features_dict["ar"]
                feature_vector.extend(ar_coeffs.flatten())
                
        return np.array(feature_vector)
    
    def train(self, X, y, classifier_type=None):
        """Train the EMG decoder with labeled data.
        
        Args:
            X (numpy.ndarray): Feature vectors for training
            y (numpy.ndarray or list): Class labels
            classifier_type (str): Which classifier to train, or None for all
            
        Returns:
            dict: Training results
        """
        if X is None or len(X) == 0 or y is None or len(y) == 0:
            logger.error("Empty training data received")
            return {"success": False, "error": "Empty training data"}
            
        results = {}
        
        # Select classifiers to train
        clf_types = [classifier_type] if classifier_type else self.classifiers.keys()
        
        for clf_type in clf_types:
            if clf_type not in self.classifiers:
                logger.warning(f"Unknown classifier: {clf_type}")
                results[clf_type] = {"success": False, "error": "Unknown classifier"}
                continue
                
            try:
                # Scale features if configured
                if self.normalize:
                    X_scaled = self.scalers[clf_type].fit_transform(X)
                else:
                    X_scaled = X
                
                # Split data
                X_train, X_test, y_train, y_test = train_test_split(
                    X_scaled, y, 
                    train_size=self.training_ratio,
                    random_state=42,
                    stratify=y
                )
                
                # Train the classifier
                self.classifiers[clf_type].fit(X_train, y_train)
                
                # Evaluate on test set
                y_pred = self.classifiers[clf_type].predict(X_test)
                accuracy = accuracy_score(y_test, y_pred)
                
                # Cross-validation
                cv_scores = cross_val_score(
                    self.classifiers[clf_type], X_scaled, y, 
                    cv=self.cv_folds
                )
                
                # Store results
                results[clf_type] = {
                    "success": True,
                    "accuracy": accuracy,
                    "cv_scores": cv_scores,
                    "cv_mean": np.mean(cv_scores),
                    "cv_std": np.std(cv_scores)
                }
                
                # Generate confusion matrix
                cm = confusion_matrix(y_test, y_pred)
                results[clf_type]["confusion_matrix"] = cm
                
                # Generate classification report
                report = classification_report(y_test, y_pred, output_dict=True)
                results[clf_type]["classification_report"] = report
                
                logger.info(f"{clf_type} classifier trained (accuracy: {accuracy:.3f})")
                
            except Exception as e:
                logger.error(f"Error training {clf_type} classifier: {str(e)}")
                results[clf_type] = {"success": False, "error": str(e)}
        
        # Overall status
        success = all(r.get("success", False) for r in results.values())
        if success:
            self.trained = True
            
        return results
    
    def predict(self, X, classifier_type=None, return_probabilities=False):
        """Predict hand/finger movements from EMG features.
        
        Args:
            X (numpy.ndarray): Feature vector for classification
            classifier_type (str): Which classifier to use, or None for voting
            return_probabilities (bool): If True, return class probabilities
            
        Returns:
            tuple: (predicted_gesture, probabilities)
        """
        if X is None or len(X) == 0:
            return None, {}
            
        # Check if any classifiers are trained
        if not self.trained:
            logger.warning("No trained classifiers available for prediction")
            return None, {}
            
        # Feature vector needs to be 2D for sklearn
        if X.ndim == 1:
            X = X.reshape(1, -1)
            
        # Select classifier to use
        if classifier_type and classifier_type in self.classifiers:
            clf_types = [classifier_type]
        else:
            # Use all available classifiers
            clf_types = list(self.classifiers.keys())
            
        # Collect predictions from each classifier
        predictions = {}
        probabilities = {}
        
        for clf_type in clf_types:
            # Skip untrained classifiers
            if not hasattr(self.classifiers[clf_type], "classes_"):
                continue
                
            try:
                # Scale features
                if self.normalize:
                    X_scaled = self.scalers[clf_type].transform(X)
                else:
                    X_scaled = X
                    
                # Get prediction
                pred = self.classifiers[clf_type].predict(X_scaled)
                predictions[clf_type] = pred[0]
                
                # Get probabilities if requested and available
                if return_probabilities and hasattr(self.classifiers[clf_type], "predict_proba"):
                    probs = self.classifiers[clf_type].predict_proba(X_scaled)[0]
                    prob_dict = {self.classifiers[clf_type].classes_[i]: probs[i] 
                                for i in range(len(probs))}
                    probabilities[clf_type] = prob_dict
                    
            except Exception as e:
                logger.error(f"Error in {clf_type} prediction: {str(e)}")
                predictions[clf_type] = None
        
        # Voting (simple majority)
        if len(predictions) > 0:
            from collections import Counter
            votes = Counter(predictions.values())
            final_prediction = votes.most_common(1)[0][0]
        else:
            final_prediction = None
            
        return final_prediction, probabilities
    
    def save_models(self, prefix=None):
        """Save trained models to disk.
        
        Args:
            prefix (str): Optional prefix for filenames
            
        Returns:
            dict: Paths to saved models
        """
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)
            
        if prefix is None:
            prefix = f"emg_decoder_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        saved_paths = {}
        
        for clf_type, clf in self.classifiers.items():
            # Skip untrained classifiers
            if not hasattr(clf, "classes_"):
                continue
                
            try:
                # Save the classifier
                model_path = os.path.join(self.model_dir, f"{prefix}_{clf_type}.pkl")
                joblib.dump(clf, model_path)
                
                # Save the scaler
                scaler_path = os.path.join(self.model_dir, f"{prefix}_{clf_type}_scaler.pkl")
                joblib.dump(self.scalers[clf_type], scaler_path)
                
                saved_paths[clf_type] = {
                    "model": model_path,
                    "scaler": scaler_path
                }
                
                logger.info(f"{clf_type} model saved to {model_path}")
                
            except Exception as e:
                logger.error(f"Error saving {clf_type} model: {str(e)}")
        
        return saved_paths
    
    def load_models(self, paths):
        """Load trained models from disk.
        
        Args:
            paths (dict): Dict with classifier types and file paths
            
        Returns:
            bool: True if successful
        """
        for clf_type, path_dict in paths.items():
            try:
                # Load the classifier
                model_path = path_dict.get("model")
                if model_path and os.path.exists(model_path):
                    self.classifiers[clf_type] = joblib.load(model_path)
                    
                # Load the scaler
                scaler_path = path_dict.get("scaler")
                if scaler_path and os.path.exists(scaler_path):
                    self.scalers[clf_type] = joblib.load(scaler_path)
                    
                logger.info(f"{clf_type} model loaded from {model_path}")
                
            except Exception as e:
                logger.error(f"Error loading {clf_type} model: {str(e)}")
                return False
        
        self.trained = True
        return True
    
    def generate_training_data_from_recordings(self, recordings_dir, out_file=None):
        """Generate training data from recorded EMG sessions.
        
        Args:
            recordings_dir (str): Directory with EMG recording files
            out_file (str): Path to save the combined dataset
            
        Returns:
            tuple: (X, y) feature matrix and labels
        """
        if not os.path.exists(recordings_dir):
            logger.error(f"Recordings directory not found: {recordings_dir}")
            return None, None
            
        X_all = []
        y_all = []
        
        # Find all h5 files in the directory
        import glob
        h5_files = glob.glob(os.path.join(recordings_dir, "*.h5"))
        
        for h5_file in h5_files:
            try:
                with h5py.File(h5_file, 'r') as f:
                    # Check if this file has the required datasets
                    if "features" not in f or "labels" not in f:
                        logger.warning(f"Skip {h5_file}: missing features or labels")
                        continue
                        
                    # Load the features and labels
                    features = f["features"][:]
                    labels = [s.decode('utf-8') for s in f["labels"][:]]
                    
                    X_all.append(features)
                    y_all.extend(labels)
                    
            except Exception as e:
                logger.error(f"Error loading {h5_file}: {str(e)}")
        
        if not X_all:
            logger.error("No valid training data found")
            return None, None
            
        # Combine all features
        X = np.vstack(X_all)
        y = np.array(y_all)
        
        # Save the combined dataset if requested
        if out_file:
            try:
                with h5py.File(out_file, 'w') as f:
                    f.create_dataset("features", data=X)
                    
                    # Convert labels to ASCII strings
                    labels_ascii = np.array([s.encode('ascii') for s in y])
                    f.create_dataset("labels", data=labels_ascii, dtype='S100')
                    
                logger.info(f"Combined training data saved to {out_file}")
                
            except Exception as e:
                logger.error(f"Error saving combined dataset: {str(e)}")
        
        return X, y
    
    def plot_confusion_matrix(self, cm, class_names=None):
        """Plot the confusion matrix for visualization.
        
        Args:
            cm (numpy.ndarray): Confusion matrix
            class_names (list): Class labels
        """
        if class_names is None:
            class_names = self.gesture_names[:len(cm)]
            
        # Create figure
        plt.figure(figsize=(10, 8))
        plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
        plt.title('Confusion Matrix')
        plt.colorbar()
        
        # Add labels
        tick_marks = np.arange(len(class_names))
        plt.xticks(tick_marks, class_names, rotation=45, ha="right")
        plt.yticks(tick_marks, class_names)
        
        # Add values inside cells
        thresh = cm.max() / 2.
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                plt.text(j, i, format(cm[i, j], 'd'),
                        ha="center", va="center",
                        color="white" if cm[i, j] > thresh else "black")
        
        plt.tight_layout()
        plt.ylabel('True Gesture')
        plt.xlabel('Predicted Gesture')
        plt.show()


if __name__ == "__main__":
    # Simple test script
    
    # Create synthetic training data
    n_samples = 500
    n_features = 64 * 4  # 4 features per channel with 64 channels
    
    # Create random feature vectors
    X = np.random.rand(n_samples, n_features)
    
    # Use a subset of gesture names
    gesture_subset = ["thumb_flexion", "index_flexion", "middle_flexion", 
                     "ring_little_flexion", "power_grip", "rest"]
    
    # Create random labels
    y = np.random.choice(gesture_subset, size=n_samples)
    
    # Create and train the decoder
    decoder = EMGDecoder()
    
    results = decoder.train(X, y)
    
    for clf_type, result in results.items():
        if result["success"]:
            print(f"{clf_type} accuracy: {result['accuracy']:.3f}")
            print(f"{clf_type} cross-validation mean: {result['cv_mean']:.3f} ± {result['cv_std']:.3f}")
            
            # Plot confusion matrix
            decoder.plot_confusion_matrix(result["confusion_matrix"], gesture_subset)
    
    # Test prediction
    test_sample = np.random.rand(1, n_features)
    prediction, probs = decoder.predict(test_sample[0], return_probabilities=True)
    
    print(f"Predicted gesture: {prediction}")
    
    # Save models
    decoder.save_models("test_model")