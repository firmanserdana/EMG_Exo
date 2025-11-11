%% Individual Subject Time-Series Visualization
% Displays raw sEMG signals normalized by MVC
% 32 channels divided into 4 figures (8 channels each)
% Shows 9 trials: 3 conditions × 3 repetitions

clear; clc; close all;

%% Configuration
subject_id = '08'; % Change this to analyze different subjects
conditions = {'no_glove', 'passive_glove', 'active_glove'};
condition_names = {'No Glove', 'Passive Glove', 'Active Glove'};
n_repetitions = 3;
n_channels = 32;
n_conditions = length(conditions);

% Sampling frequency (Hz)
fs = 1000; % Adjust if your sampling rate is different

% Bandpass filter parameters for sEMG
lowcut = 20;   % Hz - high-pass to remove motion artifacts
highcut = 450; % Hz - low-pass to remove high-frequency noise
filter_order = 4;

% Color scheme: same condition uses same color family with subtle brightness variations
% Index 1-3: No Glove (blue), 4-6: Passive Glove (green), 7-9: Active Glove (pink)
colors = [
    0.0, 0.3, 0.7;  % No Glove Rep1 - dark blue
    0.1, 0.4, 0.8;  % No Glove Rep2 - medium blue
    0.2, 0.5, 0.9;  % No Glove Rep3 - light blue
    0.0, 0.6, 0.3;  % Passive Glove Rep1 - dark green
    0.1, 0.7, 0.4;  % Passive Glove Rep2 - medium green
    0.2, 0.8, 0.5;  % Passive Glove Rep3 - light green
    0.9, 0.2, 0.5;  % Active Glove Rep1 - dark pink
    1.0, 0.3, 0.6;  % Active Glove Rep2 - medium pink
    1.0, 0.5, 0.7   % Active Glove Rep3 - light pink
];

% Line properties
line_width = 0.8; % Thinner lines

fprintf('Visualizing Subject %s Time-Series Data\n', subject_id);
fprintf('=========================================\n\n');

%% Check subject folder
subject_folder = ['S' subject_id];
if ~exist(subject_folder, 'dir')
    error('Subject folder not found: %s', subject_folder);
end

%% Load MVC data
fprintf('Loading MVC data...\n');
possible_mvc_names = {
    sprintf('emg_data_mvc_%s.csv', subject_id),
    sprintf('emg_data_mvc_01_%s.csv', subject_id),
    'emg_data_mvc_01.csv',
    'emg_data_mvc.csv'
};

mvc_vector = [];
for i = 1:length(possible_mvc_names)
    mvc_filename = fullfile(subject_folder, possible_mvc_names{i});
    if exist(mvc_filename, 'file')
        try
            mvc_data = readmatrix(mvc_filename);
            mvc_vector = max(abs(mvc_data), [], 1);
            fprintf('MVC loaded: %s\n', possible_mvc_names{i});
            break;
        catch
        end
    end
end

if isempty(mvc_vector)
    error('MVC file not found for Subject %s', subject_id);
end

%% Design Butterworth bandpass filter for sEMG
fprintf('\nDesigning bandpass filter: %d-%d Hz\n', lowcut, highcut);
[b, a] = butter(filter_order, [lowcut, highcut]/(fs/2), 'bandpass');
fprintf('Filter applied: %dth order Butterworth bandpass\n', filter_order);

%% Load all trial data
fprintf('\nLoading trial data...\n');

trial_data = cell(n_conditions, n_repetitions);
trial_labels = cell(n_conditions, n_repetitions);
trial_idx = 0;

for c = 1:n_conditions
    condition = conditions{c};
    
    for r = 1:n_repetitions
        trial_idx = trial_idx + 1;
        
        possible_names = {
            sprintf('emg_data_%s_%02d_%s.csv', condition, r, subject_id),
            sprintf('emg_data_%s_0%d_%s.csv', condition, r, subject_id),
            sprintf('emg_data_%s_%d_%s.csv', condition, r, subject_id)
        };
        
        file_loaded = false;
        for i = 1:length(possible_names)
            filename = fullfile(subject_folder, possible_names{i});
            if exist(filename, 'file')
                try
                    data = readmatrix(filename);
                    
                    % Apply bandpass filter to each channel
                    data_filtered = zeros(size(data));
                    for ch = 1:size(data, 2)
                        data_filtered(:, ch) = filtfilt(b, a, data(:, ch));
                    end
                    
                    % Rectify (absolute value)
                    data_rectified = abs(data_filtered);
                    
                    % Apply RMS envelope (moving average for smoothing)
                    window_size = 50; % 50ms window at 1000Hz
                    data_envelope = zeros(size(data_rectified));
                    for ch = 1:size(data_rectified, 2)
                        data_envelope(:, ch) = movmean(data_rectified(:, ch), window_size);
                    end
                    
                    % Normalize by MVC
                    data_normalized = data_envelope ./ mvc_vector;
                    
                    trial_data{c, r} = data_normalized;
                    trial_labels{c, r} = sprintf('%s Rep%d', condition_names{c}, r);
                    fprintf('  Loaded: %s [%d samples]\n', possible_names{i}, size(data, 1));
                    file_loaded = true;
                    break;
                catch ME
                    fprintf('  Error loading %s: %s\n', possible_names{i}, ME.message);
                end
            end
        end
        
        if ~file_loaded
            warning('File not found: %s, rep %d', condition, r);
            trial_data{c, r} = [];
            trial_labels{c, r} = '';
        end
    end
end

%% Create 4 figures (8 channels each)
fprintf('\nGenerating plots...\n');

channels_per_fig = 8;
n_figures = ceil(n_channels / channels_per_fig);

for fig_idx = 1:n_figures
    % Determine channel range for this figure
    ch_start = (fig_idx - 1) * channels_per_fig + 1;
    ch_end = min(fig_idx * channels_per_fig, n_channels);
    channels_in_fig = ch_start:ch_end;
    n_ch_fig = length(channels_in_fig);
    
    % Create figure
    figure('Position', [100 + (fig_idx-1)*50, 100 + (fig_idx-1)*50, 1400, 900]);
    
    % Plot each channel
    for subplot_idx = 1:n_ch_fig
        ch = channels_in_fig(subplot_idx);
        
        subplot(n_ch_fig, 1, subplot_idx);
        hold on;
        
        legend_entries = {};
        
        % Plot all trials
        for c = 1:n_conditions
            for r = 1:n_repetitions
                if ~isempty(trial_data{c, r})
                    % Calculate color index: condition determines base (1-3, 4-6, 7-9)
                    % repetition determines offset within that group
                    color_idx = (c - 1) * n_repetitions + r;
                    
                    data = trial_data{c, r}(:, ch);
                    time = (0:length(data)-1)' / fs; % Time in seconds
                    
                    plot(time, data, 'Color', colors(color_idx, :), 'LineWidth', line_width);
                    legend_entries{end+1} = trial_labels{c, r};
                end
            end
        end
        
        hold off;
        
        % Formatting
        ylabel(sprintf('Ch%d\n(%% MVC)', ch), 'FontSize', 9, 'FontWeight', 'bold');
        grid on;
        xlim([0, inf]); % Auto-adjust to data
        
        % Only show x-label on bottom subplot
        if subplot_idx == n_ch_fig
            xlabel('Time (s)', 'FontSize', 10);
        else
            set(gca, 'XTickLabel', []);
        end
        
        % Only show legend on top subplot
        if subplot_idx == 1
            legend(legend_entries, 'Location', 'eastoutside', 'FontSize', 8, ...
                   'Orientation', 'vertical');
            title(sprintf('Subject %s - Channels %d-%d', subject_id, ch_start, ch_end), ...
                  'FontSize', 12, 'FontWeight', 'bold');
        end
        
        set(gca, 'FontSize', 8);
    end
    
    fprintf('  Figure %d: Channels %d-%d complete\n', fig_idx, ch_start, ch_end);
end

%% Summary statistics
fprintf('\n=== Summary Statistics ===\n');
fprintf('Subject: %s\n', subject_id);
fprintf('Total trials loaded: %d/%d\n', sum(~cellfun(@isempty, trial_data(:))), ...
        n_conditions * n_repetitions);

for c = 1:n_conditions
    valid_trials = 0;
    total_samples = 0;
    
    for r = 1:n_repetitions
        if ~isempty(trial_data{c, r})
            valid_trials = valid_trials + 1;
            total_samples = total_samples + size(trial_data{c, r}, 1);
        end
    end
    
    if valid_trials > 0
        avg_duration = total_samples / valid_trials / fs; % seconds
        fprintf('  %s: %d trials, avg duration: %.2f s\n', ...
                condition_names{c}, valid_trials, avg_duration);
    end
end

fprintf('\n=== Visualization Complete ===\n');