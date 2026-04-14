%% =========================================================
%  Rehabilitation Glove — Pilot Patient Study Results
%  Nature sub-journal style | Exo vs No-Exo | 7 Tasks
%
%  Layout:  Row 1 = Tasks 1–3  |  Row 2 = Tasks 4–7
%  No background shading. Tasks visually grouped by a thin
%  border rectangle drawn around each task's sub-panels.
%
%  Run in MATLAB R2020b or later.
%  Output: rehab_glove_results.pdf  +  rehab_glove_results.png
% =========================================================
clear; clc; close all;

%% ---- 1. DATA -----------------------------------------------

T1.S2.Exo.num    = [10, 10, 11];   T1.S2.Exo.drop   = [0, 2, 0];
T1.S2.NoExo.num  = [8,  13, 14];   T1.S2.NoExo.drop  = [1, 1, 1];
T1.S3.Exo.num    = [14, 14, 13];   T1.S3.Exo.drop   = [0, 0, 0];
T1.S3.NoExo.num  = [25, 27, 30];   T1.S3.NoExo.drop  = [1, 1, 1];
T1.S4.Exo.num    = [10,  9, 12];   T1.S4.Exo.drop   = [0, 0, 0];
T1.S4.NoExo.num  = [7,   4,  6];   T1.S4.NoExo.drop  = [2, 0, 2];

T2.S2.Exo.time   = [29.5,  17.0,  30.0  ];  T2.S2.Exo.score   = [1, 1, 1];
T2.S2.NoExo.time = [24.55, NaN,   NaN   ];  T2.S2.NoExo.score = [0, 0, 0];
T2.S3.Exo.time   = [17.0,  15.06, 34.46 ];  T2.S3.Exo.score   = [4, 4, 4];
T2.S3.NoExo.time = [14.42, 15.92, 11.33 ];  T2.S3.NoExo.score = [3, 3, 3];

T3.S2.Exo.time   = [56.61, 50.59, 43.96 ];  T3.S2.Exo.score   = [3, 3, 3];
T3.S2.NoExo.time = [31.04, 20.02, 16.88 ];  T3.S2.NoExo.score = [3, 3, 3];
T3.S3.Exo.time   = [40.16, 36.57, 35.34 ];  T3.S3.Exo.score   = [4, 4, 4];
T3.S3.NoExo.time = [20.65, 22.86, 18.47 ];  T3.S3.NoExo.score = [4, 3, 3];

T4.S2.Exo.time   = [88.78, 70.97, 79.02 ];  T4.S2.Exo.score   = [4, 5, 4];
T4.S2.NoExo.time = [42.84, 33.52, 31.28 ];  T4.S2.NoExo.score = [4, 4, 4];
T4.S3.Exo.time   = [93.60, 79.51, 54.83 ];  T4.S3.Exo.score   = [4, 4, 5];
T4.S3.NoExo.time = [53.60, 32.63, 29.77 ];  T4.S3.NoExo.score = [3, 5, 5];

T5.S3.Exo.time   = [8.34,  10.62, 11.79 ];
T5.S3.NoExo.time = [8.25,  14.49,  9.71 ];
T5.S4.Exo.time   = [12.79, 11.94,  9.19 ];
T5.S4.NoExo.time = [9.96,   8.00,  7.09 ];

T6.S3.Exo.time   = [15.31, 19.64, 15.19 ];
T6.S3.NoExo.time = [10.61,  9.52, 10.29 ];
T6.S4.Exo.time   = [10.96,  9.79,  9.30 ];
T6.S4.NoExo.time = [6.23,   6.53,  8.86 ];

T7.S3.Exo.time   = [19.75, 16.48, 14.89 ];
T7.S3.NoExo.time = [23.54, 15.67,  8.93 ];

%% ---- 2. STYLE PARAMETERS -----------------------------------

C_Exo   = [0.18 0.42 0.72];
C_NoExo = [0.84 0.35 0.18];
C_ring  = [0.82 0.10 0.10];

C_S2 = [0.12 0.12 0.12];
C_S3 = [0.40 0.40 0.40];
C_S4 = [0.68 0.68 0.68];

alpha_tr = 0.40;
sz_tr    = 24;
sz_mn    = 62;
lw_mn    = 2.2;
lw_cn    = 0.9;
lw_ring  = 1.5;
jitter   = 0.07;

mk_S2 = 'o'; mk_S3 = '^'; mk_S4 = 's';

fn      = 'Helvetica';
fs_lbl  = 7;
fs_tick = 6.5;
fs_ttl  = 7.5;
fs_ann  = 5.8;
fs_cond = 6.0;

C_all = {C_S2, C_S3, C_S4};  mk_all = {mk_S2, mk_S3, mk_S4};
C_23  = {C_S2, C_S3};         mk_23  = {mk_S2, mk_S3};
C_34  = {C_S3, C_S4};         mk_34  = {mk_S3, mk_S4};
C_3   = {C_S3};                mk_3   = {mk_S3};

%% ---- 3. FIGURE LAYOUT --------------------------------------
%  7 data columns + 1 legend column = 8 columns total
%  Row 1 cols 0-5: T1num, T1drop, T2time, T2score, T3time, T3score
%  Row 2 cols 0-4: T4time, T4score, T5time, T6time, T7time
%  Legend: col 6 (tall, spans both rows)

fig = figure('Units','centimeters','Position',[2 2 23 12], ...
             'Color','white','PaperPositionMode','auto');

nC   = 8;
gap_x = 0.040;   % gap between individual sub-panels
gap_y = 0.13;
pad_l = 0.068; pad_r = 0.015; pad_t = 0.06; pad_b = 0.125;

w  = (1 - pad_l - pad_r - (nC-1)*gap_x) / nC;
h  = (1 - pad_t - pad_b - gap_y) / 2;

yr1 = pad_b + h + gap_y;   % top row bottom edge
yr2 = pad_b;               % bottom row bottom edge
xc  = pad_l + (0:nC-1) .* (w + gap_x);

% Helper: create an axes at grid (col, row)  [0-indexed col, 0=top row]
P = @(col,row) [xc(col+1), yr1*(row==0)+yr2*(row==1), w, h];

%% ---- 4. DRAW TASK GROUP BORDERS ----------------------------
%  A thin light-grey rectangle is drawn around each task group
%  (task title + its sub-panels) so readers can see task boundaries.
%  We compute each group's bounding box in figure-normalised units.

inner_pad = 0.006;   % inset from panel edges
title_top = pad_t;   % extra height to include title text above panels

% Row 1 task groups: [col_start, col_end, row]
r1_groups = {[0 1], [2 3], [4 5]};   % Task1, Task2, Task3
r2_groups = {[0 1], [2 2], [3 3], [4 4]};  % Task4, Task5, Task6, Task7

for g = 1:numel(r1_groups)
    c0 = r1_groups{g}(1); c1 = r1_groups{g}(2);
    bx = xc(c0+1) - inner_pad;
    by = yr1 - inner_pad;
    bw = (xc(c1+1) + w) - xc(c0+1) + 2*inner_pad;
    bh = h + inner_pad + title_top*0.6;
    annotation('rectangle',[bx by bw bh], ...
        'Color',[0.78 0.78 0.78],'LineWidth',0.6);
end
for g = 1:numel(r2_groups)
    c0 = r2_groups{g}(1); c1 = r2_groups{g}(2);
    bx = xc(c0+1) - inner_pad;
    by = yr2 - inner_pad;
    bw = (xc(c1+1) + w) - xc(c0+1) + 2*inner_pad;
    bh = h + inner_pad + title_top*0.6;
    annotation('rectangle',[bx by bw bh], ...
        'Color',[0.78 0.78 0.78],'LineWidth',0.6);
end

%% ---- 5. ROW 1: TASKS 1, 2, 3 -------------------------------

% -- Task 1a: Number of blocks --
ax = axes('Position',P(0,0));
styleAx(ax,'Number of blocks',[0 10 20 30],[0 36],fn,fs_lbl,fs_tick,fs_cond);
taskTitle(ax,'Task 1','[standard]',true,fn,fs_ttl,fs_ann); addN(ax,3,fn,fs_ann);
plotStrip(ax, ...
    {T1.S2.NoExo.num, T1.S3.NoExo.num, T1.S4.NoExo.num}, ...
    {T1.S2.Exo.num,   T1.S3.Exo.num,   T1.S4.Exo.num}, ...
    {false, true, false}, {false, false, false}, ...
    C_all, mk_all, C_NoExo, C_Exo, C_ring, ...
    alpha_tr, sz_tr, sz_mn, lw_mn, lw_cn, lw_ring, jitter);

% -- Task 1b: Drops --
ax = axes('Position',P(1,0));
styleAx(ax,'Drops',[0 1 2 3],[-0.3 3.7],fn,fs_lbl,fs_tick,fs_cond);
addN(ax,3,fn,fs_ann);
plotStrip(ax, ...
    {T1.S2.NoExo.drop, T1.S3.NoExo.drop, T1.S4.NoExo.drop}, ...
    {T1.S2.Exo.drop,   T1.S3.Exo.drop,   T1.S4.Exo.drop}, ...
    {false, true, false}, {false, false, false}, ...
    C_all, mk_all, C_NoExo, C_Exo, C_ring, ...
    alpha_tr, sz_tr, sz_mn, lw_mn, lw_cn, lw_ring, jitter);

% -- Task 2a: Time --
ax = axes('Position',P(2,0));
styleAx(ax,'Time (s)',[0 10 20 30 40],[0 43],fn,fs_lbl,fs_tick,fs_cond);
taskTitle(ax,'Task 2','[standard]',true,fn,fs_ttl,fs_ann); addN(ax,2,fn,fs_ann);
plotStrip(ax, ...
    {T2.S2.NoExo.time, T2.S3.NoExo.time}, ...
    {T2.S2.Exo.time,   T2.S3.Exo.time}, ...
    {false, false}, {false, false}, ...
    C_23, mk_23, C_NoExo, C_Exo, C_ring, ...
    alpha_tr, sz_tr, sz_mn, lw_mn, lw_cn, lw_ring, jitter);
yl = ax.YLim;
text(ax, 0.80, 24.55+(yl(2)-yl(1))*0.05, '†', ...
    'FontSize',fs_ann+1.5,'Color',C_S2,'FontName',fn, ...
    'HorizontalAlignment','center','FontWeight','bold');

% -- Task 2b: Score --
ax = axes('Position',P(3,0));
styleAx(ax,'Score',[0 1 2 3 4 5],[-0.3 5.7],fn,fs_lbl,fs_tick,fs_cond);
addN(ax,2,fn,fs_ann);
plotStrip(ax, ...
    {T2.S2.NoExo.score, T2.S3.NoExo.score}, ...
    {T2.S2.Exo.score,   T2.S3.Exo.score}, ...
    {false, false}, {false, false}, ...
    C_23, mk_23, C_NoExo, C_Exo, C_ring, ...
    alpha_tr, sz_tr, sz_mn, lw_mn, lw_cn, lw_ring, jitter);

% -- Task 3a: Time --
ax = axes('Position',P(4,0));
styleAx(ax,'Time (s)',[0 20 40 60],[0 70],fn,fs_lbl,fs_tick,fs_cond);
taskTitle(ax,'Task 3','[standard]',true,fn,fs_ttl,fs_ann); addN(ax,2,fn,fs_ann);
plotStrip(ax, ...
    {T3.S2.NoExo.time, T3.S3.NoExo.time}, ...
    {T3.S2.Exo.time,   T3.S3.Exo.time}, ...
    {false, false}, {false, false}, ...
    C_23, mk_23, C_NoExo, C_Exo, C_ring, ...
    alpha_tr, sz_tr, sz_mn, lw_mn, lw_cn, lw_ring, jitter);

% -- Task 3b: Score --
ax = axes('Position',P(5,0));
styleAx(ax,'Score',[2 3 4 5],[1.5 5.6],fn,fs_lbl,fs_tick,fs_cond);
addN(ax,2,fn,fs_ann);
plotStrip(ax, ...
    {T3.S2.NoExo.score, T3.S3.NoExo.score}, ...
    {T3.S2.Exo.score,   T3.S3.Exo.score}, ...
    {false, false}, {false, false}, ...
    C_23, mk_23, C_NoExo, C_Exo, C_ring, ...
    alpha_tr, sz_tr, sz_mn, lw_mn, lw_cn, lw_ring, jitter);

%% ---- 6. ROW 2: TASKS 4, 5, 6, 7 ----------------------------

% -- Task 4a: Time --
ax = axes('Position',P(0,1));
styleAx(ax,'Time (s)',[0 30 60 90],[0 110],fn,fs_lbl,fs_tick,fs_cond);
taskTitle(ax,'Task 4','[standard]',true,fn,fs_ttl,fs_ann); addN(ax,2,fn,fs_ann);
plotStrip(ax, ...
    {T4.S2.NoExo.time, T4.S3.NoExo.time}, ...
    {T4.S2.Exo.time,   T4.S3.Exo.time}, ...
    {false, false}, {false, false}, ...
    C_23, mk_23, C_NoExo, C_Exo, C_ring, ...
    alpha_tr, sz_tr, sz_mn, lw_mn, lw_cn, lw_ring, jitter);

% -- Task 4b: Score --
ax = axes('Position',P(1,1));
styleAx(ax,'Score',[2 3 4 5],[1.5 5.6],fn,fs_lbl,fs_tick,fs_cond);
addN(ax,2,fn,fs_ann);
plotStrip(ax, ...
    {T4.S2.NoExo.score, T4.S3.NoExo.score}, ...
    {T4.S2.Exo.score,   T4.S3.Exo.score}, ...
    {false, false}, {false, false}, ...
    C_23, mk_23, C_NoExo, C_Exo, C_ring, ...
    alpha_tr, sz_tr, sz_mn, lw_mn, lw_cn, lw_ring, jitter);

% -- Task 5: Time only --
ax = axes('Position',P(2,1));
styleAx(ax,'Time (s)',[0 5 10 15],[0 18],fn,fs_lbl,fs_tick,fs_cond);
taskTitle(ax,'Task 5','[time only]',false,fn,fs_ttl,fs_ann); addN(ax,2,fn,fs_ann);
plotStrip(ax, ...
    {T5.S3.NoExo.time, T5.S4.NoExo.time}, ...
    {T5.S3.Exo.time,   T5.S4.Exo.time}, ...
    {false, true}, {false, false}, ...
    C_34, mk_34, C_NoExo, C_Exo, C_ring, ...
    alpha_tr, sz_tr, sz_mn, lw_mn, lw_cn, lw_ring, jitter);

% -- Task 6: Time only --
ax = axes('Position',P(3,1));
styleAx(ax,'Time (s)',[0 5 10 15 20],[0 25],fn,fs_lbl,fs_tick,fs_cond);
taskTitle(ax,'Task 6','[time only]',false,fn,fs_ttl,fs_ann); addN(ax,2,fn,fs_ann);
plotStrip(ax, ...
    {T6.S3.NoExo.time, T6.S4.NoExo.time}, ...
    {T6.S3.Exo.time,   T6.S4.Exo.time}, ...
    {true, true}, {false, false}, ...
    C_34, mk_34, C_NoExo, C_Exo, C_ring, ...
    alpha_tr, sz_tr, sz_mn, lw_mn, lw_cn, lw_ring, jitter);

% -- Task 7: Time only (n=1, S3 only) --
ax = axes('Position',P(4,1));
styleAx(ax,'Time (s)',[0 10 20],[0 28],fn,fs_lbl,fs_tick,fs_cond);
taskTitle(ax,'Task 7','[time only]',false,fn,fs_ttl,fs_ann); addN(ax,1,fn,fs_ann);
plotStrip(ax, ...
    {T7.S3.NoExo.time}, ...
    {T7.S3.Exo.time}, ...
    {false}, {false}, ...
    C_3, mk_3, C_NoExo, C_Exo, C_ring, ...
    alpha_tr, sz_tr, sz_mn, lw_mn, lw_cn, lw_ring, jitter);
yl7 = ax.YLim; xl7 = ax.XLim;
text(ax, mean(xl7), yl7(1)+(yl7(2)-yl7(1))*0.10, 'S4: unable', ...
    'FontSize',fs_ann-0.5,'Color',[0.55 0.55 0.55],'FontName',fn, ...
    'HorizontalAlignment','center','FontAngle','italic');

%% ---- 7. LEGEND (col 6, tall, spans both rows) --------------
ax_l = axes('Position',[xc(7), yr2, w*1.6, h*2+gap_y]);
axis(ax_l,'off');  hold on;
ax_l.XLim = [0 1.2];  ax_l.YLim = [0 1];

lx = 0.04;  tx = 0.28;  ly = 0.97;  st = 0.082;

% -- Condition --
text(ax_l,lx,ly,'Condition','FontSize',fs_ann,'FontName',fn, ...
    'VerticalAlignment','middle','FontWeight','bold','Color',[0.25 0.25 0.25]);
ly = ly - st;
fill(ax_l,[lx lx+0.19 lx+0.19 lx],[ly-0.022 ly-0.022 ly+0.022 ly+0.022], ...
    C_NoExo,'EdgeColor','none');
text(ax_l,tx,ly,'No glove Glove','FontSize',fs_ann,'FontName',fn,'VerticalAlignment','middle');
ly = ly - st;
fill(ax_l,[lx lx+0.19 lx+0.19 lx],[ly-0.022 ly-0.022 ly+0.022 ly+0.022], ...
    C_Exo,'EdgeColor','none');
text(ax_l,tx,ly,'Glove Glove','FontSize',fs_ann,'FontName',fn,'VerticalAlignment','middle');

% -- Subject --
ly = ly - st*1.2;
text(ax_l,lx,ly,'Subject','FontSize',fs_ann,'FontName',fn, ...
    'VerticalAlignment','middle','FontWeight','bold','Color',[0.25 0.25 0.25]);
Cs  = {C_S2,  C_S3,  C_S4};
mks = {mk_S2, mk_S3, mk_S4};
lbs = {'S2',  'S3',  'S4'};
for idx = 1:3
    ly = ly - st;
    scatter(ax_l, lx+0.095, ly, sz_tr*0.65, Cs{idx}, mks{idx}, 'filled', ...
        'MarkerFaceAlpha',0.85,'MarkerEdgeColor','none');
    text(ax_l, tx, ly, sprintf('Subject %s',lbs{idx}), ...
        'FontSize',fs_ann,'FontName',fn,'VerticalAlignment','middle');
end

% -- Markers --
ly = ly - st*1.2;
text(ax_l,lx,ly,'Markers','FontSize',fs_ann,'FontName',fn, ...
    'VerticalAlignment','middle','FontWeight','bold','Color',[0.25 0.25 0.25]);

ly = ly - st;
scatter(ax_l, lx+0.095, ly, sz_mn*0.60, [0.25 0.25 0.25], 'o', 'filled', ...
    'MarkerEdgeColor','w','LineWidth',0.5);
text(ax_l, tx, ly, 'Mean (3 trials)','FontSize',fs_ann,'FontName',fn,'VerticalAlignment','middle');

ly = ly - st;
scatter(ax_l, lx+0.095, ly, sz_tr*0.65, [0.25 0.25 0.25], 'o', 'filled', ...
    'MarkerFaceAlpha',0.35,'MarkerEdgeColor','none');
text(ax_l, tx, ly, 'Individual trial','FontSize',fs_ann,'FontName',fn,'VerticalAlignment','middle');

ly = ly - st;
plot(ax_l, [lx lx+0.19], [ly ly], '--', 'Color',[0.40 0.40 0.40 0.60], 'LineWidth',0.9);
text(ax_l, tx, ly, 'Glovein-subject','FontSize',fs_ann,'FontName',fn,'VerticalAlignment','middle');

ly = ly - st;
plot(ax_l, [lx lx+0.19], [ly ly], '-', 'Color',[0.50 0.50 0.50], 'LineWidth',lw_mn);
text(ax_l, tx, ly, 'Group mean','FontSize',fs_ann,'FontName',fn,'VerticalAlignment','middle');

ly = ly - st;
scatter(ax_l, lx+0.095, ly, sz_mn*0.60, [0.35 0.35 0.35], 'o', 'filled', ...
    'MarkerEdgeColor','w','LineWidth',0.5);
theta = linspace(0, 2*pi, 64);
plot(ax_l, lx+0.095 + 0.055*cos(theta), ly + 0.030*sin(theta), ...
    '-','Color',C_ring,'LineWidth',lw_ring);
text(ax_l, tx, ly, 'Wrist comp.','FontSize',fs_ann,'FontName',fn,'VerticalAlignment','middle');

% -- Notes --
ly = ly - st*1.2;
text(ax_l,lx,ly,'† S2 Task 2: only T1 possible', ...
    'FontSize',fs_ann-0.5,'FontName',fn,'VerticalAlignment','middle', ...
    'FontAngle','italic','Color',[0.50 0.50 0.50]);
ly = ly - st*0.78;
text(ax_l,lx,ly,'  No glove glove', ...
    'FontSize',fs_ann-0.5,'FontName',fn,'VerticalAlignment','middle', ...
    'FontAngle','italic','Color',[0.50 0.50 0.50]);
ly = ly - st*0.78;
text(ax_l,lx,ly,'n = subjects per task', ...
    'FontSize',fs_ann-0.5,'FontName',fn,'VerticalAlignment','middle', ...
    'FontAngle','italic','Color',[0.50 0.50 0.50]);

%% ---- 8. FOOTNOTE -------------------------------------------
annotation('textbox',[pad_l, 0.002, 1-pad_l-pad_r, 0.055], ...
    'String',['Red ring = wrist compensation (tenodesis or wrist supination instead of normal grasp).  ', ...
              '† S2 Task 2: T2/T3 not completable No glove glove.  ', ...
              'Colored axis labels indicate condition (orange = No glove glove; blue = Glove glove).  ', ...
              'Grey box outlines group sub-panels belonging to the same task.  ', ...
              'n = subjects per task.  Dashed lines connect same-subject means.'], ...
    'FontSize',fs_ann-1.0,'FontName',fn,'EdgeColor','none','BackgroundColor','none', ...
    'Color',[0.45 0.45 0.45],'FitBoxToText','off','Interpreter','none');

%% ---- 9. EXPORT ---------------------------------------------
exportgraphics(fig,'rehab_glove_results.pdf','ContentType','vector','Resolution',600);
exportgraphics(fig,'rehab_glove_results.png','Resolution',600);
fprintf('\n  Saved: rehab_glove_results.pdf  /  rehab_glove_results.png\n');
print(fig, 'rehab_glove_results', '-dsvg')
exportgraphics(fig, 'rehab_glove_results.png', 'Resolution', 600)  % 保留PNG备用

%% =========================================================
%%  LOCAL FUNCTIONS
%% =========================================================

function plotStrip(ax, ne_data, ex_data, wrist_ne, wrist_ex, ...
                   colors, markers, C_ne, C_ex, C_ring, ...
                   alpha_tr, sz_tr, sz_mn, lw_mn, lw_cn, lw_ring, jitter)
% Draws strip chart on ax.
% ne_data / ex_data : cell arrays, one entry per subject, each a 1x3 vector
% wrist_ne/ex       : cell arrays of logical flags (same length as data)
% colors / markers  : cell arrays per subject

rng(42, 'twister');
n_s = numel(ne_data);
mn_ne_all = NaN(1, n_s);
mn_ex_all = NaN(1, n_s);

% Ring size: 5.5% of Y range to look consistent across panels
yl    = ax.YLim;
r_y   = (yl(2) - yl(1)) * 0.055;
r_x   = r_y * 0.35;
theta = linspace(0, 2*pi, 64);

for s = 1:n_s
    c  = colors{s};
    mk = markers{s};

    % ---- No-Exo side (x = 1) ----
    v    = ne_data{s};
    v_ok = v(~isnan(v));
    if ~isempty(v_ok)
        jit = (rand(1, numel(v_ok)) - 0.5) * jitter;
        scatter(ax, 1+jit, v_ok, sz_tr, c, mk, 'filled', ...
            'MarkerFaceAlpha', alpha_tr, ...
            'MarkerEdgeAlpha', 0, ...
            'MarkerEdgeColor', 'none');
        mn = mean(v_ok);
        mn_ne_all(s) = mn;
        scatter(ax, 1, mn, sz_mn, c, mk, 'filled', ...
            'MarkerFaceAlpha', 1.0, ...
            'MarkerEdgeColor', 'w', ...
            'LineWidth', 0.5);
        if wrist_ne{s}
            plot(ax, 1 + r_x*cos(theta), mn + r_y*sin(theta), ...
                '-', 'Color', C_ring, 'LineWidth', lw_ring, 'HitTest', 'off');
        end
    end

    % ---- Exo side (x = 2) ----
    v    = ex_data{s};
    v_ok = v(~isnan(v));
    if ~isempty(v_ok)
        jit = (rand(1, numel(v_ok)) - 0.5) * jitter;
        scatter(ax, 2+jit, v_ok, sz_tr, c, mk, 'filled', ...
            'MarkerFaceAlpha', alpha_tr, ...
            'MarkerEdgeAlpha', 0, ...
            'MarkerEdgeColor', 'none');
        mn = mean(v_ok);
        mn_ex_all(s) = mn;
        scatter(ax, 2, mn, sz_mn, c, mk, 'filled', ...
            'MarkerFaceAlpha', 1.0, ...
            'MarkerEdgeColor', 'w', ...
            'LineWidth', 0.5);
        if wrist_ex{s}
            plot(ax, 2 + r_x*cos(theta), mn + r_y*sin(theta), ...
                '-', 'Color', C_ring, 'LineWidth', lw_ring, 'HitTest', 'off');
        end
    end

    % ---- Glovein-subject connecting line ----
    if ~isnan(mn_ne_all(s)) && ~isnan(mn_ex_all(s))
        plot(ax, [1 2], [mn_ne_all(s) mn_ex_all(s)], '--', ...
            'Color', [c 0.50], 'LineWidth', lw_cn);
    end
end

% ---- Group mean bars ----
bw    = 0.16;
gm_ne = nanmean(mn_ne_all);
gm_ex = nanmean(mn_ex_all);
if ~isnan(gm_ne)
    plot(ax, [1-bw 1+bw], [gm_ne gm_ne], '-', 'Color', C_ne, 'LineWidth', lw_mn);
end
if ~isnan(gm_ex)
    plot(ax, [2-bw 2+bw], [gm_ex gm_ex], '-', 'Color', C_ex, 'LineWidth', lw_mn);
end
end

% -----------------------------------------------------------------
function styleAx(ax, ylbl, yticks, ylim, fn, fs_lbl, fs_tick, fs_cond)
hold(ax, 'on');
ax.Box        = 'off';
ax.TickDir    = 'out';
ax.TickLength = [0.025 0.025];
ax.LineWidth  = 0.8;
ax.FontName   = fn;
ax.FontSize   = fs_tick;
ax.XColor     = [0.10 0.10 0.10];
ax.YColor     = [0.10 0.10 0.10];
ax.XTick      = [1 2];
ax.XTickLabel = {};
ax.XLim       = [0.55 2.45];
ax.YTick      = yticks;
ax.YLim       = ylim;
ax.YLabel.String   = ylbl;
ax.YLabel.FontSize = fs_lbl;
ax.YLabel.FontName = fn;

% Colored bold x-axis condition labels
C_ne_lbl = [0.84 0.35 0.18];
C_ex_lbl = [0.18 0.42 0.72];
drop = (ylim(2) - ylim(1)) * 0.15;
text(ax, 1, ylim(1)-drop, 'No glove', ...
    'FontSize', fs_cond, 'FontName', fn, 'Color', C_ne_lbl, ...
    'FontWeight', 'bold', 'HorizontalAlignment', 'center', ...
    'VerticalAlignment', 'top', 'Clipping', 'off');
text(ax, 2, ylim(1)-drop, 'Glove', ...
    'FontSize', fs_cond, 'FontName', fn, 'Color', C_ex_lbl, ...
    'FontWeight', 'bold', 'HorizontalAlignment', 'center', ...
    'VerticalAlignment', 'top', 'Clipping', 'off');
end

% -----------------------------------------------------------------
function taskTitle(ax, task_str, tag_str, is_standard, fn, fs_ttl, fs_ann)
title(ax, task_str, 'FontSize', fs_ttl, 'FontName', fn, ...
    'FontWeight', 'bold', 'Color', [0.08 0.08 0.08]);
tc = [0.22 0.50 0.22];
if ~is_standard, tc = [0.50 0.50 0.50]; end
yl = ax.YLim;  xl = ax.XLim;
text(ax, mean(xl), yl(2)*0.985, tag_str, ...
    'FontSize', fs_ann-0.5, 'FontName', fn, 'Color', tc, ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
    'FontAngle', 'italic');
end

% -----------------------------------------------------------------
function addN(ax, n, fn, fs)
xl = ax.XLim;  yl = ax.YLim;
text(ax, xl(2)-0.02, yl(1)+(yl(2)-yl(1))*0.025, sprintf('n = %d', n), ...
    'FontSize', fs, 'FontName', fn, 'Color', [0.55 0.55 0.55], ...
    'HorizontalAlignment', 'right', 'VerticalAlignment', 'bottom');
end