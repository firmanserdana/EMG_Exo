import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

def plot_training_results(train_losses, valid_losses, valid_conf_matrix, axs=None, test_conf_matrix=None, keep_open=False):
    # Clear entire figure and create a new one each time
    if axs is None:
        plt.ion()
        fig, axs = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
    else:
        # Get the figure from existing axes
        fig = axs[0].figure
        fig.clear()  # Clear the figure's content
        # Create new axes within the existing figure
        axs = [fig.add_subplot(1, 3, i+1) for i in range(3)]
    
    # Col 1: Loss plot
    axs[0].plot(train_losses, label='Train Loss')
    axs[0].plot(valid_losses, label='Valid Loss')
    axs[0].set_title('Loss')
    axs[0].set_xlabel('Epoch')
    axs[0].set_ylabel('Loss')
    axs[0].legend()
    axs[0].grid(True)

    # Col 2: Validation Confusion Matrix
    axs[1].set_title('Validation Confusion Matrix')
    sns.heatmap(valid_conf_matrix, annot=True, fmt='d', cmap='Reds', 
               ax=axs[1], cbar=True)
    axs[1].set_xlabel('Predicted Label')
    axs[1].set_ylabel('True Label')

    # Col 3: Test Confusion Matrix (if available)
    axs[2].set_title('Test Confusion Matrix')
    if test_conf_matrix is not None:
        sns.heatmap(test_conf_matrix, annot=True, fmt='d', cmap='Reds', 
                   ax=axs[2], cbar=True)
        axs[2].set_xlabel('Predicted')
        axs[2].set_ylabel('True')
    else:
        axs[2].text(0.5, 0.5, 'Not available yet', ha='center', va='center', fontsize=14)
        axs[2].set_xticks([])
        axs[2].set_yticks([])
        
    plt.draw()

    if not keep_open:
        plt.pause(0.1)
    else:
        plt.show(block=True)

    return axs

def plot_predictions_with_events(fig_title, preds_times, predictions, preds_probs, events_ts, grasp_ids, 
                                save_path=None):
    """
    Plot predictions and probabilities with events and ground truth information.
    
    Parameters:
    - fig_title: title for the figure
    - preds_times: array of prediction timestamps
    - predictions: array of predicted class values
    - preds_probs: array of shape (n_times, num_classes) with class probabilities
    - events_ts: dictionary containing event timestamps for different event types
    - session_id: session identifier for the plot title
    - save_path: optional path to save the figure
    """
    
    # Create figure with 2 subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True)
    
    # Get number of classes and create color palette
    num_classes = preds_probs.shape[1]
    class_colors = plt.cm.tab10(np.arange(num_classes))
    class_range = np.arange(min(grasp_ids), max(grasp_ids)+1, 1)
    
    # Plot 1: Prediction classes
    ax1.plot(preds_times, predictions, label='Predictions', color='blue', linewidth=2)
    ax1.set_ylabel('Predicted Class')
    ax1.set_ylim(class_range[0]-0.05, class_range[-1]+0.05)
    ax1.set_yticks(class_range)
    ax1.set_xlim(preds_times[0], preds_times[-1])
    ax1.set_title(fig_title)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Plot 2: Prediction probabilities
    for class_idx in range(num_classes):
        ax2.plot(preds_times, preds_probs[:, class_idx], 
                label=f'Class {class_range[class_idx]}', color=class_colors[class_idx], linewidth=1.5)
    
    ax2.set_ylabel('Class Probabilities')
    ax2.set_xlabel('Time (s)')
    ax1.set_xlim(preds_times[0], preds_times[-1])
    ax2.set_ylim(-0.05, 1.05)
    ax2.set_yticks(np.arange(0, 1.1, 0.1))
    ax2.grid(True, alpha=0.3)
    ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    # Add event vertical lines
    event_colors = {
        'trials_start': 'green',
        'trials_end': 'red',
    }
    
    event_labels = {
        'trials_start': 'Trial Start',
        'trials_end': 'Trial End'
    }
    
    # Keep track of which labels we've already added to avoid duplicates in legend
    added_labels = set()
    
    for event_type, timestamps in events_ts.items():
        if event_type in event_colors:
            color = event_colors[event_type]
            label = event_labels[event_type]
            
            for timestamp in timestamps:
                # Only add label for the first occurrence of each event type
                current_label = label if label not in added_labels else None
                if current_label:
                    added_labels.add(label)
                
                ax1.axvline(x=timestamp, color=color, linestyle='--', alpha=0.7, 
                           linewidth=1, label=current_label)
                ax2.axvline(x=timestamp, color=color, linestyle='--', alpha=0.7, 
                           linewidth=1, label=current_label)
    
    # Add shaded areas for grasp objectives during decoding periods
    decoding_starts = events_ts['decoding_start']
    decoding_stops = events_ts['decoding_stop']
    
    for i in range(len(decoding_starts)):
        dec_start = decoding_starts[i]
        dec_stop = decoding_stops[i]
        grasp_id = int(grasp_ids[i])
        
        # Use the same color as the class probability line
        color = class_colors[grasp_id-min(grasp_ids)]
        
        # Add shaded area
        ax1.axvspan(dec_start, dec_stop, alpha=0.2, color=color, 
                    label=f'Target Class {grasp_id}' if i < num_classes else None)
        ax2.axvspan(dec_start, dec_stop, alpha=0.2, color=color,
                    label=f'Target Class {grasp_id}' if i < num_classes else None)
    
    # Update legends to include all elements
    ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    # plt.show()
    
    return fig, (ax1, ax2)