#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EMG Decoder implementation for classifying EMG signals into hand gestures.
"""

import numpy as np
import os
import time
import joblib
from datetime import datetime
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score, confusion_matrix
import logging
from typing import Dict, List, Tuple, Any, Optional, Union

from emg_exo.core.decoder.base import BaseEMGDecoder
from emg_exo.config.config import DECODING, MODEL_DIR


class EMGDecoder(BaseEMGDecoder):
    """Class for classifying EMG signals into hand gestures."""
    
    def __init__(self):
        """Initialize the EMG decoder with default settings."""
        self.classifiers = {}
        self.scaler = StandardScaler()
        self.is_trained = False
        self.features_list = DECODING["features"]
        self.logger = logging.getLogger(__name__)
        
        # Create model directory if it doesn't exist
        os.makedirs(MODEL_DIR, exist_ok=True)
        
        # Define supported hand gestures
        self.gestures = {
            0: "rest",
            1: "thumb_flexion",
            2: "thumb_extension",
            3: "thumb_pinch",
            4: "index_flexion",
            5: "index_extension",
            6: "index_pinch",
            7: "middle_flexion",
            8: "middle_extension",
            9: "middle_pinch",
            10: "ring_little_flexion",
            11: "ring_little_extension",
            12: "thumb_abduction"
        }
        
        # Initialize classifiers specified in config
        self._initialize_classifiers()
        
        self.logger.info("EMG Decoder initialized")
    
    def _initialize_classifiers(self):
        """Initialize the requested classifiers."""
        classifier_names = DECODING["classifiers"]
        
        for name in classifier_names:
            if name == "kNN":
                # k-Nearest Neighbors classifier
                self.classifiers["kNN"] = KNeighborsClassifier(
                    n_neighbors=5,
                    weights='distance',
                    metric='euclidean'
                )
                
            elif name == "MLP":
                # Multi-layer Perceptron (neural network)
                self.classifiers["MLP"] = MLPClassifier(
                    hidden_layer_sizes=(100, 50),
                    activation='relu',
                    solver='adam',
                    alpha=0.0001,
                    batch_size='auto',
                    max_iter=500,
                    random_state=42
                )
                
        self.logger.info(f"Initialized classifiers: {list(self.classifiers.keys())}")
    
    def extract_classification_features(self, features: Dict[str, np.ndarray]) -> np.ndarray:
        """Extracts a feature vector from the feature dictionary for classification.
        
        Args:
            features: Dictionary containing features
            
        Returns:
            Feature vector for classification
        """
        return self._extract_feature_vector(features)
    
    def _extract_feature_vector(self, features: Dict[str, np.ndarray]) -> np.ndarray:
        """Extract and concatenate features into a single vector.
        
        Args:
            features: Dictionary of features from EMG processor
            
        Returns:
            Feature vector
        """
        if features is None:
            return None
            
        feature_vectors = []
        
        # Add selected features to the vector
        for feature_name in self.features_list:
            if feature_name in features and features[feature_name] is not None:
                feature_data = features[feature_name]
                
                # Reshape if necessary
                if len(feature_data.shape) > 1:
                    feature_data = feature_data.flatten()
                    
                feature_vectors.append(feature_data)
                
        # Concatenate all features into one vector
        if feature_vectors:
            return np.concatenate(feature_vectors)
        else:
            return None
    
    def train(self, training_data: np.ndarray, training_labels: np.ndarray) -> Dict[str, Any]:
        """Train the classifiers on labeled EMG data.
        
        Args:
            training_data: Feature vectors for training
            training_labels: Class labels for training
            
        Returns:
            Training performance metrics
        """
        if training_data is None or training_labels is None:
            self.logger.error("Cannot train with None data or labels")
            return None
            
        if len(training_data) != len(training_labels):
            self.logger.error(f"Data and label counts don't match: {len(training_data)} vs {len(training_labels)}")
            return None
            
        try:
            # Scale the data
            X = self.scaler.fit_transform(training_data)
            y = training_labels
            
            # Split data into training and validation sets
            test_ratio = 1.0 - DECODING["training_ratio"]
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_ratio, random_state=42, stratify=y
            )
            
            # Performance metrics
            metrics = {}
            
            # Train each classifier
            for name, clf in self.classifiers.items():
                self.logger.info(f"Training {name} classifier...")
                
                # Train the classifier
                clf.fit(X_train, y_train)
                
                # Evaluate on test set
                y_pred = clf.predict(X_test)
                accuracy = accuracy_score(y_test, y_pred)
                
                # Get cross-validation score
                cv_scores = cross_val_score(
                    clf, X, y, 
                    cv=DECODING["cv_folds"], 
                    scoring='accuracy'
                )
                
                metrics[name] = {
                    'accuracy': accuracy,
                    'cv_accuracy_mean': cv_scores.mean(),
                    'cv_accuracy_std': cv_scores.std()
                }
                
                self.logger.info(f"{name} accuracy: {accuracy:.3f}, CV: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
                
                # Generate confusion matrix
                cm = confusion_matrix(y_test, y_pred)
                metrics[name]['confusion_matrix'] = cm
            
            self.is_trained = True
            self.save_models()
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error training classifiers: {str(e)}")
            return None
    
    def classify(self, features: Union[Dict[str, np.ndarray], np.ndarray], method: str = "best") -> Tuple[Optional[int], str, float]:
        """Classify EMG features into a hand gesture.
        
        Args:
            features: EMG features from EMGProcessor or pre-extracted feature vector
            method: Classification method - "best", "kNN", "MLP", or "ensemble"
            
        Returns:
            Tuple of (gesture_id, gesture_name, confidence)
        """
        if not self.is_trained:
            if not self.load_models():
                self.logger.error("Cannot classify: No trained models available")
                return None, "unknown", 0.0
        
        try:
            # Extract features if dictionary is provided
            if isinstance(features, dict):
                feature_vector = self._extract_feature_vector(features)
                if feature_vector is None:
                    return None, "unknown", 0.0
            else:
                feature_vector = features
                
            # Ensure feature vector is 2D for sklearn
            if feature_vector.ndim == 1:
                feature_vector = feature_vector.reshape(1, -1)
                
            # Scale the features
            X = self.scaler.transform(feature_vector)
            
            # Classification result storage
            results = {}
            
            # Select classification method
            if method == "ensemble" or method == "best":
                # Use all classifiers and average/vote
                class_probabilities = np.zeros((1, len(self.gestures)))
                
                for name, clf in self.classifiers.items():
                    if hasattr(clf, 'predict_proba'):
                        # Get class probabilities if available
                        proba = clf.predict_proba(X)
                        class_probabilities += proba
                    else:
                        # Otherwise just add a vote for the predicted class
                        y_pred = clf.predict(X)[0]
                        class_probabilities[0, y_pred] += 1
                        
                # Normalize
                class_probabilities /= len(self.classifiers)
                
                # Get prediction and confidence
                prediction = np.argmax(class_probabilities)
                confidence = class_probabilities[0, prediction]
                
            elif method in self.classifiers:
                # Use a specific classifier
                clf = self.classifiers[method]
                prediction = clf.predict(X)[0]
                
                # Get confidence if available
                if hasattr(clf, 'predict_proba'):
                    confidence = clf.predict_proba(X)[0, prediction]
                else:
                    # For methods without probability, use a default
                    confidence = 1.0
                    
            else:
                self.logger.error(f"Unknown classification method: {method}")
                return None, "unknown", 0.0
                
            # Get gesture name
            gesture_name = self.gestures.get(prediction, "unknown")
            
            # Return the prediction
            return prediction, gesture_name, confidence
            
        except Exception as e:
            self.logger.error(f"Error in classification: {str(e)}")
            return None, "unknown", 0.0
    
    def save_models(self, path: Optional[str] = None) -> bool:
        """Save trained models to disk."""
        if not self.is_trained:
            self.logger.warning("Cannot save models: Models not trained")
            return False
            
        try:
            # Generate timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            save_dir = path if path is not None else MODEL_DIR
            os.makedirs(save_dir, exist_ok=True)
            
            # Save each classifier
            for name, clf in self.classifiers.items():
                model_path = os.path.join(save_dir, f"emg_classifier_{name}_{timestamp}.joblib")
                joblib.dump(clf, model_path)
                self.logger.info(f"Saved {name} model to {model_path}")
                
            # Save the scaler
            scaler_path = os.path.join(save_dir, f"emg_scaler_{timestamp}.joblib")
            joblib.dump(self.scaler, scaler_path)
            self.logger.info(f"Saved feature scaler to {scaler_path}")
            
            # Save a reference to the latest models
            latest = {
                "timestamp": timestamp,
                "classifiers": {name: f"emg_classifier_{name}_{timestamp}.joblib" for name in self.classifiers},
                "scaler": f"emg_scaler_{timestamp}.joblib"
            }
            
            import json
            latest_path = os.path.join(save_dir, "latest_models.json")
            with open(latest_path, 'w') as f:
                json.dump(latest, f, indent=2)
                
            self.logger.info("Saved model references to latest_models.json")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving models: {str(e)}")
            return False
    
    def load_models(self, path: Optional[str] = None) -> bool:
        """Load trained models from disk.
        
        Args:
            path: Optional path to load from, if different from default
            
        Returns:
            True if models loaded successfully
        """
        try:
            load_dir = path if path is not None else MODEL_DIR
            
            # Try to read the latest models reference
            import json
            latest_path = os.path.join(load_dir, "latest_models.json")
            
            if not os.path.exists(latest_path):
                self.logger.error("No saved models found")
                return False
                
            with open(latest_path, 'r') as f:
                latest = json.load(f)
                
            timestamp = latest.get("timestamp")
            
            if timestamp is None:
                self.logger.error("Invalid latest models reference")
                return False
        
            # Load classifiers
            for name in self.classifiers.keys():
                model_path = os.path.join(load_dir, f"emg_classifier_{name}_{timestamp}.joblib")
                
                if os.path.exists(model_path):
                    self.classifiers[name] = joblib.load(model_path)
                    self.logger.info(f"Loaded {name} model from {model_path}")
                else:
                    self.logger.error(f"Model file not found: {model_path}")
                    return False
            
            # Load scaler
            scaler_path = os.path.join(load_dir, f"emg_scaler_{timestamp}.joblib")
            if os.path.exists(scaler_path):
                self.scaler = joblib.load(scaler_path)
                self.logger.info(f"Loaded feature scaler from {scaler_path}")
            else:
                self.logger.error(f"Scaler file not found: {scaler_path}")
                return False
                
            self.is_trained = True
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading models: {str(e)}")
            return False
    
    def plot_confusion_matrix(self, cm, gesture_labels=None, title='Confusion Matrix'):
        """Plot a confusion matrix for classifier evaluation.
        
        Args:
            cm: Confusion matrix
            gesture_labels: Custom gesture labels
            title: Plot title
        """
        if gesture_labels is None:
            gesture_labels = [self.gestures[i] for i in range(len(self.gestures))]
            
        plt.figure(figsize=(10, 8))
        plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
        plt.title(title)
        plt.colorbar()
        
        tick_marks = np.arange(len(gesture_labels))
        plt.xticks(tick_marks, gesture_labels, rotation=45, ha='right')
        plt.yticks(tick_marks, gesture_labels)
        
        # Add text annotations
        thresh = cm.max() / 2.0
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                plt.text(j, i, format(cm[i, j], 'd'),
                         ha="center", va="center",
                         color="white" if cm[i, j] > thresh else "black")
                
        plt.tight_layout()
        plt.ylabel('True Gesture')
        plt.xlabel('Predicted Gesture')
        
        # Save the plot
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(MODEL_DIR, f"confusion_matrix_{timestamp}.png")
        plt.savefig(filename, dpi=150)
        self.logger.info(f"Saved confusion matrix to {filename}")
        
        plt.show()
