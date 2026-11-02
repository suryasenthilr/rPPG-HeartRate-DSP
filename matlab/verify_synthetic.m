function verify_synthetic()
    % VERIFY_SYNTHETIC Headless automated verification script for rPPG DSP system.
    % Generates synthetic pulsatile video, exercises the full signal processing
    % pipeline, verifies accuracy, and renders a high-resolution dashboard figure.
    %
    % Course: Digital Signal Processing (Semester 5)

    fprintf('\n========================================================================\n');
    fprintf('  RUNNING AUTOMATED rPPG SYNTHETIC BENCHMARK & VERIFICATION (MATLAB)   \n');
    fprintf('========================================================================\n\n');

    target_bpm = 72.0;
    fps = 30.0;
    n_frames = 240; % 8.0 seconds of video

    gen = SyntheticPulseGenerator(target_bpm, fps);
    tracker = FaceTracker();
    processor = RPPGSignalProcessor('method', 'green');

    fprintf('1. Initializing synthetic pulse generator (Target: %.1f BPM, Fs: %.1f Hz)...\n', target_bpm, fps);
    fprintf('2. Processing %d frames through multi-ROI tracker and DSP pipeline...\n', n_frames);

    last_frame = [];
    last_face_bbox = [];
    last_rois = [];

    tic;
    for i = 1 : n_frames
        [~, frame, timestamp] = gen.read();
        bbox = tracker.detect_face(frame);
        rois = tracker.get_rois(bbox, size(frame));
        [r, g, b] = tracker.extract_mean_rgb(frame, rois, true);
        processor.add_sample(r, g, b, timestamp);

        [smooth_bpm, raw_bpm, conf, filtered_pulse, freqs, power] = processor.process();

        last_frame = frame;
        last_face_bbox = bbox;
        last_rois = rois;
    end
    elapsed = toc;
    measured_fps = n_frames / elapsed;

    err = abs(smooth_bpm - target_bpm);
    fprintf('   Done! Processed at %.1f FPS.\n\n', measured_fps);
    fprintf('------------------------------------------------------------------------\n');
    fprintf('  VERIFICATION BENCHMARK RESULTS:\n');
    fprintf('------------------------------------------------------------------------\n');
    fprintf('  Ground Truth Target HR : %6.2f BPM\n', target_bpm);
    fprintf('  Measured Filtered HR   : %6.2f BPM\n', smooth_bpm);
    fprintf('  Instantaneous Peak HR  : %6.2f BPM\n', raw_bpm);
    fprintf('  Absolute Error         : %6.2f BPM (Tolerance: < 1.0 BPM)\n', err);
    fprintf('  Spectral SNR           : %+6.2f dB\n', processor.snr);
    fprintf('  Signal Confidence      : %6.2f %%\n', conf * 100);
    fprintf('  Empirical Fs Tracking  : %6.2f Hz\n', processor.estimate_sampling_rate());
    fprintf('------------------------------------------------------------------------\n');

    if err < 1.0
        fprintf('  STATUS: >>> BENCHMARK PASSED WITH CLINICAL PRECISION! <<<\n');
    else
        fprintf('  STATUS: >>> BENCHMARK FAILED (Error exceeded 1.0 BPM) <<<\n');
    end
    fprintf('========================================================================\n\n');

    %% Generate High-Resolution Dashboard Figure
    fprintf('Generating benchmark dashboard figure (matlab_dashboard_demo.png)...\n');
    fig = figure('Name', 'rPPG MATLAB DSP Dashboard', 'Position', [100, 100, 1280, 720], ...
                 'Color', [0.07, 0.08, 0.11], 'Visible', 'off');

    % Main Title
    annotation(fig, 'textbox', [0.05, 0.93, 0.90, 0.05], 'String', ...
               'REAL-TIME REMOTE PHOTOPLETHYSMOGRAPHY (rPPG) - DSP SEMESTER 5 BENCHMARK', ...
               'Color', [0.95, 0.95, 0.98], 'FontSize', 15, 'FontWeight', 'bold', ...
               'HorizontalAlignment', 'center', 'EdgeColor', 'none');

    % Panel 1: Video Feed with Face & ROIs
    ax1 = subplot(2, 2, 1);
    imshow(last_frame, 'Parent', ax1);
    hold(ax1, 'on');
    title(ax1, 'Spatial Multi-ROI Video Tracking', 'Color', [0.85, 0.88, 0.95], 'FontSize', 11, 'FontWeight', 'bold');

    % Draw face bounding box
    rectangle(ax1, 'Position', last_face_bbox, 'EdgeColor', [0.2, 0.8, 1.0], 'LineWidth', 2);
    % Draw Forehead ROI
    rectangle(ax1, 'Position', last_rois.forehead, 'EdgeColor', [0.2, 0.9, 0.3], 'LineWidth', 1.8);
    % Draw Cheeks ROIs
    rectangle(ax1, 'Position', last_rois.left_cheek, 'EdgeColor', [1.0, 0.8, 0.2], 'LineWidth', 1.8);
    rectangle(ax1, 'Position', last_rois.right_cheek, 'EdgeColor', [1.0, 0.8, 0.2], 'LineWidth', 1.8);
    % Draw Central ROI
    rectangle(ax1, 'Position', last_rois.central, 'EdgeColor', [0.9, 0.3, 0.9], 'LineWidth', 1.8);

    text(ax1, last_rois.forehead(1), last_rois.forehead(2) - 8, 'Forehead ROI', ...
         'Color', [0.2, 0.9, 0.3], 'FontSize', 9, 'FontWeight', 'bold');
    text(ax1, last_face_bbox(1), last_face_bbox(2) + last_face_bbox(4) + 18, ...
         sprintf('Face Tracked [Deadband Active] | Frame: %d', n_frames), ...
         'Color', [0.2, 0.8, 1.0], 'FontSize', 9);
    hold(ax1, 'off');

    % Panel 2: Telemetry HUD Card
    ax2 = subplot(2, 2, 2);
    set(ax2, 'Color', [0.10, 0.12, 0.16], 'XColor', 'none', 'YColor', 'none');
    title(ax2, 'Clinical Telemetry & DSP Performance', 'Color', [0.85, 0.88, 0.95], 'FontSize', 11, 'FontWeight', 'bold');

    text(ax2, 0.50, 0.78, sprintf('%.1f BPM', smooth_bpm), ...
         'Color', [0.25, 0.95, 0.45], 'FontSize', 34, 'FontWeight', 'bold', ...
         'HorizontalAlignment', 'center');

    if conf >= 0.70
        gauge_str = '● OPTIMAL SIGNAL QUALITY';
        gauge_col = [0.2, 0.9, 0.3];
    elseif conf >= 0.50
        gauge_str = '● GOOD SIGNAL QUALITY';
        gauge_col = [0.2, 0.8, 1.0];
    elseif conf >= 0.25
        gauge_str = '● STABILIZING / ACQUIRING';
        gauge_col = [1.0, 0.75, 0.2];
    else
        gauge_str = '● WEAK / LOW CONFIDENCE';
        gauge_col = [1.0, 0.3, 0.3];
    end

    text(ax2, 0.50, 0.58, gauge_str, 'Color', gauge_col, 'FontSize', 12, ...
         'FontWeight', 'bold', 'HorizontalAlignment', 'center');

    info_str = {
        sprintf('Ground Truth Target   : %.1f BPM', target_bpm), ...
        sprintf('Estimation Error      : %.2f BPM', err), ...
        sprintf('Spectral SNR (dB)     : %+5.1f dB', processor.snr), ...
        sprintf('Confidence Metric     : %.1f %%', conf * 100), ...
        sprintf('Empirical Sampling Fs : %.2f Hz', processor.estimate_sampling_rate()), ...
        'Extraction Mode       : Green Channel (-G/L)', ...
        'Bandpass Filter       : 4th-Order Zero-Phase (0.75-3.0 Hz)'
    };
    text(ax2, 0.10, 0.28, info_str, 'Color', [0.80, 0.85, 0.92], 'FontSize', 10, ...
         'FontName', 'Courier', 'Interpreter', 'none');

    % Panel 3: Oscilloscope Time-Domain BVP Waveform
    ax3 = subplot(2, 2, 3);
    set(ax3, 'Color', [0.05, 0.06, 0.09], 'XColor', [0.6, 0.65, 0.75], 'YColor', [0.6, 0.65, 0.75]);
    grid(ax3, 'on');
    set(ax3, 'GridColor', [0.25, 0.28, 0.35], 'GridAlpha', 0.5);
    hold(ax3, 'on');

    if ~isempty(filtered_pulse)
        t_axis = (0 : length(filtered_pulse) - 1) / fps;
        plot(ax3, t_axis, filtered_pulse, 'Color', [0.2, 0.95, 0.4], 'LineWidth', 1.8);
        yline(ax3, 0, '--', 'Color', [0.4, 0.45, 0.55], 'LineWidth', 1.0);
        xlim(ax3, [0, max(1.0, t_axis(end))]);
        ylim(ax3, [-2.8, 2.8]);
    end
    title(ax3, 'Real-Time Blood Volume Pulse (BVP) [Filtered Time-Domain]', ...
          'Color', [0.85, 0.88, 0.95], 'FontSize', 11, 'FontWeight', 'bold');
    xlabel(ax3, 'Time (seconds)', 'Color', [0.75, 0.80, 0.90]);
    ylabel(ax3, 'Normalized Amplitude (\sigma)', 'Color', [0.75, 0.80, 0.90]);
    hold(ax3, 'off');

    % Panel 4: Windowed FFT Power Spectrum
    ax4 = subplot(2, 2, 4);
    set(ax4, 'Color', [0.05, 0.06, 0.09], 'XColor', [0.6, 0.65, 0.75], 'YColor', [0.6, 0.65, 0.75]);
    grid(ax4, 'on');
    set(ax4, 'GridColor', [0.25, 0.28, 0.35], 'GridAlpha', 0.5);
    hold(ax4, 'on');

    if ~isempty(freqs) && ~isempty(power)
        bpm_axis = freqs * 60.0;
        plot(ax4, bpm_axis, power, 'Color', [0.2, 0.8, 1.0], 'LineWidth', 1.8);

        % Mark peak
        peak_freq = raw_bpm / 60.0;
        xline(ax4, raw_bpm, '-.', 'Color', [1.0, 0.3, 0.3], 'LineWidth', 1.6);
        text(ax4, raw_bpm + 3, 0.85, sprintf('f_{peak} = %.2f Hz\n(%.1f BPM)', peak_freq, raw_bpm), ...
             'Color', [1.0, 0.4, 0.4], 'FontSize', 9, 'FontWeight', 'bold');

        xlim(ax4, [40, 180]);
        ylim(ax4, [0, 1.05]);
    end
    title(ax4, 'Zero-Padded Windowed FFT Spectrum (Hanning, N=2048)', ...
          'Color', [0.85, 0.88, 0.95], 'FontSize', 11, 'FontWeight', 'bold');
    xlabel(ax4, 'Heart Rate (BPM)', 'Color', [0.75, 0.80, 0.90]);
    ylabel(ax4, 'Normalized Spectral Power', 'Color', [0.75, 0.80, 0.90]);
    hold(ax4, 'off');

    % Save output image in root workspace
    output_path = fullfile(pwd, 'matlab_dashboard_demo.png');
    exportgraphics(fig, output_path, 'Resolution', 150);
    close(fig);
    fprintf('Dashboard saved successfully to: %s\n\n', output_path);
end
