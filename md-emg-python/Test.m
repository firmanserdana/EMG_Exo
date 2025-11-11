%% Flexible sEMG Data Analysis with MVC Normalization
% Channel-wise statistical analysis across subjects

clear; clc; close all;

%% 1. Configuration
% subjects = {'00', '01', '02', '03', '04', '05', '06', '07', '08'}; % Single subject: {'01'}, Multiple: {'01', '02', '03', '04', '05'}、
 subjects = {'08'}; 
conditions = {'no_glove', 'passive_glove', 'active_glove'};
n_repetitions = 3;
n_channels = 32;

n_subjects = length(subjects);
n_conditions = length(conditions);

fprintf('Analysis Mode: %d Subject(s)\n', n_subjects);

%% 2. Check file structure
fprintf('\n===== Checking File Structure =====\n');

for s = 1:n_subjects
    subject_id = subjects{s};
    subject_folder = ['S' subject_id];
    
    if exist(subject_folder, 'dir')
        fprintf('Subject %s folder: OK\n', subject_id);
        csv_files = dir(fullfile(subject_folder, '*.csv'));
        fprintf('  Found %d CSV files\n', length(csv_files));
    else
        error('Subject %s folder NOT FOUND: %s', subject_id, subject_folder);
    end
end

%% 3. Initialize data structures
% Raw data: (condition, repetition, subject, channel)
data_matrix = NaN(n_conditions, n_repetitions, n_subjects, n_channels);
mvc_matrix = NaN(n_subjects, n_channels);

%% 4. Read MVC data
fprintf('\n===== Reading MVC Data =====\n');

for s = 1:n_subjects
    subject_id = subjects{s};
    subject_folder = ['S' subject_id];
    
    possible_mvc_names = {
        sprintf('emg_data_mvc_%s.csv', subject_id),
        sprintf('emg_data_mvc_01_%s.csv', subject_id),
        'emg_data_mvc_01.csv',
        'emg_data_mvc.csv'
    };
    
    mvc_loaded = false;
    for i = 1:length(possible_mvc_names)
        mvc_filename = fullfile(subject_folder, possible_mvc_names{i});
        if exist(mvc_filename, 'file')
            try
                mvc_data = readmatrix(mvc_filename);
                mvc_matrix(s, :) = max(abs(mvc_data), [], 1);
                fprintf('Subject %s MVC: OK (%s)\n', subject_id, possible_mvc_names{i});
                mvc_loaded = true;
                break;
            catch
            end
        end
    end
    
    if ~mvc_loaded
        error('MVC file not found for Subject %s', subject_id);
    end
end

%% 5. Read condition data
fprintf('\n===== Reading Condition Data =====\n');

for s = 1:n_subjects
    subject_id = subjects{s};
    subject_folder = ['S' subject_id];
    fprintf('Subject %s:\n', subject_id);
    
    for c = 1:n_conditions
        condition = conditions{c};
        
        for r = 1:n_repetitions
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
                        channel_means = mean(abs(data), 1, 'omitnan')';
                        data_matrix(c, r, s, :) = channel_means;
                        fprintf('  %s: OK\n', possible_names{i});
                        file_loaded = true;
                        break;
                    catch
                    end
                end
            end
            
            if ~file_loaded
                warning('File not found: %s, rep %d', condition, r);
            end
        end
    end
end

%% 6. MVC Normalization
fprintf('\n===== MVC Normalization =====\n');

data_normalized = NaN(size(data_matrix));

for s = 1:n_subjects
    for ch = 1:n_channels
        mvc_value = mvc_matrix(s, ch);
        if ~isnan(mvc_value) && mvc_value > 0
            data_normalized(:, :, s, ch) = data_matrix(:, :, s, ch) / mvc_value;
        end
    end
end

fprintf('Normalization complete.\n');

%% 7. Outlier removal
all_data = data_normalized(:);
global_mean = mean(all_data, 'omitnan');
global_std = std(all_data, 'omitnan');
threshold = 3;

outlier_mask = (data_normalized < global_mean - threshold*global_std) | ...
               (data_normalized > global_mean + threshold*global_std);
data_normalized(outlier_mask) = NaN;

fprintf('Outliers removed: %d\n', sum(outlier_mask(:)));

%% 8. Analysis
condition_names = {'No Glove', 'Passive Glove', 'Active Glove'};

if n_subjects == 1
    %% Single Subject Analysis
    fprintf('\n===== SINGLE SUBJECT ANALYSIS =====\n');
    fprintf('Subject: %s\n\n', subjects{1});
    
    % Overall statistics
    fprintf('Overall Statistics (Mean ± SD):\n');
    fprintf('%-15s | Mean (%%MVC) | SD (%%MVC)\n', 'Condition');
    fprintf('----------------|-------------|----------\n');
    
    for c = 1:n_conditions
        condition_data = squeeze(data_normalized(c, :, 1, :));
        fprintf('%-15s | %11.4f | %9.4f\n', condition_names{c}, ...
                mean(condition_data(:), 'omitnan'), std(condition_data(:), 'omitnan'));
    end
    
    % Channel-wise statistics
    fprintf('\n===== Channel-wise Statistics =====\n');
    fprintf('Ch  | No Glove    | Passive     | Active\n');
    fprintf('    | Mean ± SD   | Mean ± SD   | Mean ± SD\n');
    fprintf('----|-------------|-------------|-------------\n');
    
    channel_means = zeros(n_channels, n_conditions);
    channel_stds = zeros(n_channels, n_conditions);
    
    for ch = 1:n_channels
        fprintf('%2d  |', ch);
        for c = 1:n_conditions
            rep_data = squeeze(data_normalized(c, :, 1, ch));
            ch_mean = mean(rep_data, 'omitnan');
            ch_std = std(rep_data, 'omitnan');
            channel_means(ch, c) = ch_mean;
            channel_stds(ch, c) = ch_std;
            fprintf(' %.3f±%.3f |', ch_mean, ch_std);
        end
        fprintf('\n');
    end
    
    % Single figure with error bars
    figure('Position', [100, 100, 1200, 700]);
    bar(channel_means);
    hold on;
    
    ngroups = n_channels;
    nbars = n_conditions;
    groupwidth = min(0.8, nbars/(nbars + 1.5));
    for c = 1:nbars
        x = (1:ngroups) - groupwidth/2 + (2*c-1) * groupwidth / (2*nbars);
        errorbar(x, channel_means(:,c), channel_stds(:,c), 'k.', 'LineWidth', 1);
    end
    hold off;
    
    title(['Subject ' subjects{1} ' - Channel-wise Comparison'], ...
          'FontSize', 14, 'FontWeight', 'bold');
    xlabel('Channel Number', 'FontSize', 12);
    ylabel('%MVC', 'FontSize', 12);
    legend(condition_names, 'Location', 'best', 'FontSize', 11);
    xlim([0 33]);
    grid on;
    set(gca, 'FontSize', 10);
    
else
    %% Multiple Subjects Analysis
    fprintf('\n===== MULTIPLE SUBJECTS ANALYSIS =====\n');
    fprintf('Number of subjects: %d\n\n', n_subjects);
    
    % Calculate mean for each subject, condition, and channel
    % Average across repetitions: (subject, condition, channel)
    subject_condition_channel_means = zeros(n_subjects, n_conditions, n_channels);
    
    for s = 1:n_subjects
        for c = 1:n_conditions
            for ch = 1:n_channels
                rep_data = squeeze(data_normalized(c, :, s, ch)); % 3 repetitions
                subject_condition_channel_means(s, c, ch) = mean(rep_data, 'omitnan');
            end
        end
    end
    
    % Grand average across subjects
    fprintf('===== Grand Average Across Subjects =====\n');
    fprintf('%-15s | Mean (%%MVC) | SD (%%MVC)\n', 'Condition');
    fprintf('----------------|-------------|----------\n');
    
    for c = 1:n_conditions
        all_channels_data = squeeze(subject_condition_channel_means(:, c, :));
        fprintf('%-15s | %11.4f | %9.4f\n', condition_names{c}, ...
                mean(all_channels_data(:), 'omitnan'), ...
                std(all_channels_data(:), 'omitnan'));
    end
    
    % Channel-wise statistical analysis
    fprintf('\n===== Channel-wise Statistical Analysis =====\n');
    
    if n_subjects >= 3
        fprintf('Performing Friedman test for each channel...\n\n');
        fprintf('Ch  | No Glove  | Passive   | Active    | p-value | Sig\n');
        fprintf('    | Mean±SD   | Mean±SD   | Mean±SD   |         |\n');
        fprintf('----|-----------|-----------|-----------|---------|----\n');
        
        p_values = zeros(n_channels, 1);
        
        for ch = 1:n_channels
            % Extract data for this channel: (subjects x conditions)
            channel_data = squeeze(subject_condition_channel_means(:, :, ch));
            
            % Calculate means and SDs
            means = mean(channel_data, 1, 'omitnan');
            sds = std(channel_data, 0, 1, 'omitnan');
            
            % Friedman test
            try
                [p, ~, ~] = friedman(channel_data, 1, 'off');
                p_values(ch) = p;
                sig_marker = '';
                if p < 0.001
                    sig_marker = '***';
                elseif p < 0.01
                    sig_marker = '**';
                elseif p < 0.05
                    sig_marker = '*';
                end
                
                fprintf('%2d  | %.3f±%.3f | %.3f±%.3f | %.3f±%.3f | %.4f | %s\n', ...
                        ch, means(1), sds(1), means(2), sds(2), means(3), sds(3), ...
                        p, sig_marker);
            catch
                fprintf('%2d  | %.3f±%.3f | %.3f±%.3f | %.3f±%.3f | N/A     |\n', ...
                        ch, means(1), sds(1), means(2), sds(2), means(3), sds(3));
            end
        end
        
        fprintf('\nSignificance levels: * p<0.05, ** p<0.01, *** p<0.001\n');
        
        % Summary
        n_sig = sum(p_values < 0.05);
        fprintf('\nSummary: %d/%d channels show significant differences (p<0.05)\n', ...
                n_sig, n_channels);
        
        % Post-hoc analysis for significant channels
        sig_channels = find(p_values < 0.05);
        if ~isempty(sig_channels)
            fprintf('\n===== Post-hoc Analysis for Significant Channels =====\n');
            
            for i = 1:length(sig_channels)
                ch = sig_channels(i);
                fprintf('\nChannel %d (p=%.4f):\n', ch, p_values(ch));
                
                channel_data = squeeze(subject_condition_channel_means(:, :, ch));
                
                % Check for valid data before pairwise tests
                valid_1 = ~isnan(channel_data(:,1));
                valid_2 = ~isnan(channel_data(:,2));
                valid_3 = ~isnan(channel_data(:,3));
                
                % No Glove vs Passive
                valid_12 = valid_1 & valid_2;
                if sum(valid_12) >= 3
                    p1 = signrank(channel_data(valid_12,1), channel_data(valid_12,2));
                    fprintf('  No Glove vs Passive:  p=%.4f', p1);
                    if p1 < 0.05, fprintf(' *'); end
                    fprintf('\n');
                else
                    fprintf('  No Glove vs Passive:  insufficient data\n');
                end
                
                % No Glove vs Active
                valid_13 = valid_1 & valid_3;
                if sum(valid_13) >= 3
                    p2 = signrank(channel_data(valid_13,1), channel_data(valid_13,3));
                    fprintf('  No Glove vs Active:   p=%.4f', p2);
                    if p2 < 0.05, fprintf(' *'); end
                    fprintf('\n');
                else
                    fprintf('  No Glove vs Active:   insufficient data\n');
                end
                
                % Passive vs Active
                valid_23 = valid_2 & valid_3;
                if sum(valid_23) >= 3
                    p3 = signrank(channel_data(valid_23,2), channel_data(valid_23,3));
                    fprintf('  Passive vs Active:    p=%.4f', p3);
                    if p3 < 0.05, fprintf(' *'); end
                    fprintf('\n');
                else
                    fprintf('  Passive vs Active:    insufficient data\n');
                end
            end
        end
        
    else
        % Not enough subjects for statistics
        fprintf('Not enough subjects (n=%d) for statistical testing.\n', n_subjects);
        fprintf('Showing descriptive statistics only:\n\n');
        
        fprintf('Ch  | No Glove  | Passive   | Active\n');
        fprintf('    | Mean±SD   | Mean±SD   | Mean±SD\n');
        fprintf('----|-----------|-----------|----------\n');
        
        for ch = 1:n_channels
            channel_data = squeeze(subject_condition_channel_means(:, :, ch));
            means = mean(channel_data, 1, 'omitnan');
            sds = std(channel_data, 0, 1, 'omitnan');
            
            fprintf('%2d  | %.3f±%.3f | %.3f±%.3f | %.3f±%.3f\n', ...
                    ch, means(1), sds(1), means(2), sds(2), means(3), sds(3));
        end
    end
    
    % Visualization: Grand average only
    figure('Position', [100, 100, 1200, 700]);
    
    grand_means = zeros(n_channels, n_conditions);
    grand_sds = zeros(n_channels, n_conditions);
    
    for ch = 1:n_channels
        for c = 1:n_conditions
            channel_data = squeeze(subject_condition_channel_means(:, c, ch));
            grand_means(ch, c) = mean(channel_data, 'omitnan');
            grand_sds(ch, c) = std(channel_data, 'omitnan');
        end
    end
    
    bar(grand_means);
    hold on;
    
    ngroups = n_channels;
    nbars = n_conditions;
    groupwidth = min(0.8, nbars/(nbars + 1.5));
    for c = 1:nbars
        x = (1:ngroups) - groupwidth/2 + (2*c-1) * groupwidth / (2*nbars);
        errorbar(x, grand_means(:,c), grand_sds(:,c), 'k.', 'LineWidth', 1);
    end
    hold off;
    
    title(['Grand Average - ' num2str(n_subjects) ' Subjects'], ...
          'FontSize', 14, 'FontWeight', 'bold');
    xlabel('Channel Number', 'FontSize', 12);
    ylabel('%MVC', 'FontSize', 12);
    legend(condition_names, 'Location', 'best', 'FontSize', 11);
    xlim([0 33]);
    grid on;
    set(gca, 'FontSize', 10);
    
    % Highlight significant channels if applicable
    if n_subjects >= 3 && exist('p_values', 'var')
        sig_ch = find(p_values < 0.05);
        if ~isempty(sig_ch)
            hold on;
            for i = 1:length(sig_ch)
                plot(sig_ch(i), max(grand_means(sig_ch(i),:)) + 0.05, 'r*', 'MarkerSize', 10);
            end
            hold off;
            legend([condition_names, {'Significant (p<0.05)'}], 'Location', 'best', 'FontSize', 11);
        end
    end
end

fprintf('\n===== Analysis Complete =====\n');