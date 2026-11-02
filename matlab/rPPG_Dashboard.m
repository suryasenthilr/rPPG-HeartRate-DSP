function rPPG_Dashboard(varargin)
    % RPPG_DASHBOARD Interactive Real-Time Oscilloscope Dashboard GUI for MATLAB
    %
    % Usage:
    %   rPPG_Dashboard()                                     % Default: Synthetic Generator
    %   rPPG_Dashboard('source', 'synthetic', 'bpm', 75)     % Synthetic at 75 BPM
    %   rPPG_Dashboard('source', 'webcam')                   % Live USB Webcam
    %   rPPG_Dashboard('source', 'video.mp4')                % Offline Video File
    %   rPPG_Dashboard('method', 'chrom')                    % CHROM Subspace Projection
    %
    % Course: Digital Signal Processing (Semester 5)

    p = inputParser;
    addParameter(p, 'source', 'synthetic', @(x) ischar(x) || isstring(x));
    addParameter(p, 'method', 'green', @ischar);
    addParameter(p, 'bpm', 72.0, @isnumeric);
    parse(p, varargin{:});

    source = char(p.Results.source);
    method = char(p.Results.method);
    target_bpm = double(p.Results.bpm);

    fprintf('\n========================================================================\n');
    fprintf('  STARTING rPPG REAL-TIME OSCILLOSCOPE DASHBOARD (MATLAB)              \n');
    fprintf('  Source: %s | Method: %s                                               \n', source, upper(method));
    fprintf('========================================================================\n\n');

    %% Initialize Components
    processor = RPPGSignalProcessor('method', method);
    tracker = FaceTracker();

    video_reader = [];
    cam = [];
    synthetic_gen = [];

    if strcmpi(source, 'synthetic')
        synthetic_gen = SyntheticPulseGenerator(target_bpm, 30.0);
    elseif strcmpi(source, 'webcam')
        if isempty(which('webcam'))
            warning('MATLAB Webcam Support Package is not installed. Falling back to Synthetic mode.');
            source = 'synthetic';
            synthetic_gen = SyntheticPulseGenerator(target_bpm, 30.0);
        else
            try
                cam = webcam();
            catch ME
                warning('Could not open webcam: %s. Falling back to Synthetic mode.', ME.message);
                source = 'synthetic';
                synthetic_gen = SyntheticPulseGenerator(target_bpm, 30.0);
            end
        end
    else
        % Video file
        if exist(source, 'file')
            video_reader = VideoReader(source);
        else
            warning('Video file "%s" not found. Falling back to Synthetic mode.', source);
            source = 'synthetic';
            synthetic_gen = SyntheticPulseGenerator(target_bpm, 30.0);
        end
    end

    %% Build Dashboard Figure
    fig = figure('Name', 'rPPG Cardiovascular DSP Dashboard (Semester 5)', ...
                 'NumberTitle', 'off', ...
                 'Position', [80, 80, 1320, 740], ...
                 'Color', [0.07, 0.08, 0.11], ...
                 'MenuBar', 'none', ...
                 'ToolBar', 'none', ...
                 'CloseRequestFcn', @on_close);

    % State flags
    is_running = true;
    is_paused = false;

    % Top Banner
    uicontrol(fig, 'Style', 'text', 'String', 'REAL-TIME rPPG CARDIOVASCULAR DSP SYSTEM — SEMESTER 5', ...
              'Units', 'normalized', 'Position', [0.05, 0.94, 0.90, 0.04], ...
              'BackgroundColor', [0.07, 0.08, 0.11], 'ForegroundColor', [0.95, 0.96, 0.98], ...
              'FontSize', 14, 'FontWeight', 'bold');

    % Control Buttons Panel
    btn_panel = uipanel(fig, 'Units', 'normalized', 'Position', [0.03, 0.02, 0.94, 0.06], ...
                        'BackgroundColor', [0.10, 0.12, 0.16], 'BorderType', 'none');

    h_btn_pause = uicontrol(btn_panel, 'Style', 'pushbutton', 'String', 'Pause Feed', ...
                            'Units', 'normalized', 'Position', [0.02, 0.15, 0.18, 0.70], ...
                            'BackgroundColor', [0.20, 0.25, 0.35], 'ForegroundColor', 'white', ...
                            'FontSize', 10, 'FontWeight', 'bold', 'Callback', @on_pause);

    h_btn_method = uicontrol(btn_panel, 'Style', 'pushbutton', ...
                             'String', sprintf('Mode: %s (Click to Toggle)', upper(processor.method)), ...
                             'Units', 'normalized', 'Position', [0.23, 0.15, 0.26, 0.70], ...
                             'BackgroundColor', [0.15, 0.40, 0.35], 'ForegroundColor', 'white', ...
                             'FontSize', 10, 'FontWeight', 'bold', 'Callback', @on_toggle_method);

    uicontrol(btn_panel, 'Style', 'pushbutton', 'String', 'Reset DSP Buffers', ...
              'Units', 'normalized', 'Position', [0.52, 0.15, 0.22, 0.70], ...
              'BackgroundColor', [0.45, 0.30, 0.15], 'ForegroundColor', 'white', ...
              'FontSize', 10, 'FontWeight', 'bold', 'Callback', @on_reset);

    uicontrol(btn_panel, 'Style', 'pushbutton', 'String', 'Exit System', ...
              'Units', 'normalized', 'Position', [0.77, 0.15, 0.20, 0.70], ...
              'BackgroundColor', [0.50, 0.15, 0.15], 'ForegroundColor', 'white', ...
              'FontSize', 10, 'FontWeight', 'bold', 'Callback', @on_close);

    % Subplot 1: Video Feed (Left)
    ax_video = subplot('Position', [0.04, 0.12, 0.44, 0.78], 'Parent', fig);
    set(ax_video, 'Color', [0.05, 0.06, 0.08], 'XColor', 'none', 'YColor', 'none');
    title(ax_video, 'Facial Microvascular Multi-ROI Tracking', 'Color', [0.85, 0.90, 0.95], 'FontSize', 11, 'FontWeight', 'bold');

    % Subplot 2: Telemetry HUD Card (Top Right)
    ax_telemetry = subplot('Position', [0.52, 0.64, 0.44, 0.26], 'Parent', fig);
    set(ax_telemetry, 'Color', [0.10, 0.12, 0.17], 'XColor', 'none', 'YColor', 'none');
    title(ax_telemetry, 'Clinical Cardiovascular Telemetry', 'Color', [0.85, 0.90, 0.95], 'FontSize', 11, 'FontWeight', 'bold');

    h_bpm_text = text(ax_telemetry, 0.50, 0.75, '-- BPM', ...
                      'Color', [0.25, 0.95, 0.45], 'FontSize', 36, 'FontWeight', 'bold', ...
                      'HorizontalAlignment', 'center');

    h_gauge_text = text(ax_telemetry, 0.50, 0.48, '● ACQUIRING CARDIAC SIGNAL...', ...
                        'Color', [1.0, 0.75, 0.2], 'FontSize', 12, 'FontWeight', 'bold', ...
                        'HorizontalAlignment', 'center');

    h_info_text = text(ax_telemetry, 0.10, 0.22, 'Initializing buffers...', ...
                       'Color', [0.80, 0.85, 0.92], 'FontSize', 9, 'FontName', 'Courier');

    % Subplot 3: Live BVP Oscilloscope (Middle Right)
    ax_wave = subplot('Position', [0.52, 0.38, 0.44, 0.22], 'Parent', fig);
    set(ax_wave, 'Color', [0.05, 0.06, 0.09], 'XColor', [0.6, 0.65, 0.75], 'YColor', [0.6, 0.65, 0.75]);
    grid(ax_wave, 'on');
    set(ax_wave, 'GridColor', [0.25, 0.28, 0.35], 'GridAlpha', 0.5);
    title(ax_wave, 'Blood Volume Pulse (BVP) [4th-Order Zero-Phase Butterworth]', ...
          'Color', [0.85, 0.90, 0.95], 'FontSize', 10, 'FontWeight', 'bold');
    xlabel(ax_wave, 'Time (seconds)', 'Color', [0.75, 0.80, 0.90], 'FontSize', 9);
    ylabel(ax_wave, 'Amplitude (\sigma)', 'Color', [0.75, 0.80, 0.90], 'FontSize', 9);
    hold(ax_wave, 'on');
    h_wave_line = plot(ax_wave, [0, 1], [0, 0], 'Color', [0.2, 0.95, 0.4], 'LineWidth', 1.8);
    yline(ax_wave, 0, '--', 'Color', [0.4, 0.45, 0.55], 'LineWidth', 1.0);
    ylim(ax_wave, [-2.8, 2.8]);
    hold(ax_wave, 'off');

    % Subplot 4: FFT Power Spectrum (Bottom Right)
    ax_fft = subplot('Position', [0.52, 0.12, 0.44, 0.22], 'Parent', fig);
    set(ax_fft, 'Color', [0.05, 0.06, 0.09], 'XColor', [0.6, 0.65, 0.75], 'YColor', [0.6, 0.65, 0.75]);
    grid(ax_fft, 'on');
    set(ax_fft, 'GridColor', [0.25, 0.28, 0.35], 'GridAlpha', 0.5);
    title(ax_fft, 'Windowed FFT Power Spectrum (Hanning Window, N=2048)', ...
          'Color', [0.85, 0.90, 0.95], 'FontSize', 10, 'FontWeight', 'bold');
    xlabel(ax_fft, 'Heart Rate (BPM)', 'Color', [0.75, 0.80, 0.90], 'FontSize', 9);
    ylabel(ax_fft, 'Normalized Power', 'Color', [0.75, 0.80, 0.90], 'FontSize', 9);
    hold(ax_fft, 'on');
    h_fft_line = plot(ax_fft, [45, 180], [0, 0], 'Color', [0.2, 0.8, 1.0], 'LineWidth', 1.8);
    h_fft_peak = xline(ax_fft, 72, '-.', 'Color', [1.0, 0.3, 0.3], 'LineWidth', 1.5, 'Visible', 'off');
    xlim(ax_fft, [45, 180]);
    ylim(ax_fft, [0, 1.05]);
    hold(ax_fft, 'off');

    %% Video Image Display Handle
    h_img = [];
    h_face_rect = [];
    h_roi_forehead = [];
    h_roi_lcheek = [];
    h_roi_rcheek = [];
    h_roi_central = [];

    %% Callbacks
    function on_pause(~, ~)
        is_paused = ~is_paused;
        if is_paused
            set(h_btn_pause, 'String', 'Resume Feed', 'BackgroundColor', [0.45, 0.35, 0.15]);
        else
            set(h_btn_pause, 'String', 'Pause Feed', 'BackgroundColor', [0.20, 0.25, 0.35]);
        end
    end

    function on_toggle_method(~, ~)
        if strcmpi(processor.method, 'green')
            processor.method = 'chrom';
        else
            processor.method = 'green';
        end
        processor.reset();
        set(h_btn_method, 'String', sprintf('Mode: %s (Click to Toggle)', upper(processor.method)));
    end

    function on_reset(~, ~)
        processor.reset();
    end

    function on_close(~, ~)
        is_running = false;
        delete(fig);
        if ~isempty(cam)
            delete(cam);
        end
    end

    %% Main Real-Time Processing Loop
    frame_count = 0;
    fps_timer = tic;
    live_fps = 30.0;

    while is_running && ishandle(fig)
        if is_paused
            pause(0.05);
            continue;
        end

        % 1. Acquire Frame
        has_frame = false;
        frame = [];
        t_stamp = toc(fps_timer);

        if ~isempty(synthetic_gen)
            [has_frame, frame, t_stamp] = synthetic_gen.read();
        elseif ~isempty(cam)
            try
                frame = snapshot(cam);
                has_frame = true;
            catch
                has_frame = false;
            end
        elseif ~isempty(video_reader)
            if hasFrame(video_reader)
                frame = readFrame(video_reader);
                has_frame = true;
            else
                % Loop video
                video_reader.CurrentTime = 0;
                continue;
            end
        end

        if ~has_frame || isempty(frame)
            pause(0.03);
            continue;
        end

        frame_count = frame_count + 1;
        if frame_count >= 15
            elapsed_sec = toc(fps_timer);
            live_fps = frame_count / elapsed_sec;
            frame_count = 0;
            fps_timer = tic;
        end

        % 2. Face and Anatomical ROI Tracking
        bbox = tracker.detect_face(frame);
        rois = tracker.get_rois(bbox, size(frame));
        [r, g, b] = tracker.extract_mean_rgb(frame, rois, true);

        % 3. Feed to DSP Pipeline
        processor.add_sample(r, g, b, t_stamp);
        [smooth_bpm, raw_bpm, conf, filtered_pulse, freqs, power] = processor.process();

        % 4. Render Video Frame and Overlay Rectangles
        if isempty(h_img) || ~ishandle(h_img)
            axes(ax_video); %#ok<LAXES>
            h_img = imshow(frame, 'Parent', ax_video);
            hold(ax_video, 'on');
            h_face_rect = rectangle(ax_video, 'Position', bbox, 'EdgeColor', [0.2, 0.8, 1.0], 'LineWidth', 2);
            h_roi_forehead = rectangle(ax_video, 'Position', rois.forehead, 'EdgeColor', [0.2, 0.9, 0.3], 'LineWidth', 1.8);
            h_roi_lcheek = rectangle(ax_video, 'Position', rois.left_cheek, 'EdgeColor', [1.0, 0.8, 0.2], 'LineWidth', 1.8);
            h_roi_rcheek = rectangle(ax_video, 'Position', rois.right_cheek, 'EdgeColor', [1.0, 0.8, 0.2], 'LineWidth', 1.8);
            h_roi_central = rectangle(ax_video, 'Position', rois.central, 'EdgeColor', [0.9, 0.3, 0.9], 'LineWidth', 1.8);
            hold(ax_video, 'off');
        else
            set(h_img, 'CData', frame);
            set(h_face_rect, 'Position', bbox);
            set(h_roi_forehead, 'Position', rois.forehead);
            set(h_roi_lcheek, 'Position', rois.left_cheek);
            set(h_roi_rcheek, 'Position', rois.right_cheek);
            set(h_roi_central, 'Position', rois.central);
        end

        % 5. Update Telemetry HUD
        if smooth_bpm > 0
            set(h_bpm_text, 'String', sprintf('%.1f BPM', smooth_bpm));
        else
            set(h_bpm_text, 'String', '-- BPM');
        end

        if conf >= 0.70
            set(h_gauge_text, 'String', '● OPTIMAL SIGNAL QUALITY', 'Color', [0.25, 0.95, 0.45]);
        elseif conf >= 0.50
            set(h_gauge_text, 'String', '● GOOD SIGNAL QUALITY', 'Color', [0.20, 0.85, 1.00]);
        elseif conf >= 0.25
            set(h_gauge_text, 'String', '● STABILIZING / ACQUIRING', 'Color', [1.00, 0.75, 0.20]);
        else
            set(h_gauge_text, 'String', '● WEAK / LOW CONFIDENCE', 'Color', [1.00, 0.35, 0.35]);
        end

        fs_val = processor.estimate_sampling_rate();
        info_line = sprintf('SNR: %+5.1f dB | Conf: %3.0f%% | FPS: %4.1f | Fs: %4.1f Hz | Mode: %s', ...
                            processor.snr, conf * 100, live_fps, fs_val, upper(processor.method));
        set(h_info_text, 'String', info_line);

        % 6. Update Oscilloscope BVP Plot
        if ~isempty(filtered_pulse) && length(filtered_pulse) > 10
            t_axis = (0 : length(filtered_pulse) - 1) / fs_val;
            set(h_wave_line, 'XData', t_axis, 'YData', filtered_pulse);
            xlim(ax_wave, [0, max(1.0, t_axis(end))]);
        end

        % 7. Update FFT Power Spectrum Plot
        if ~isempty(freqs) && ~isempty(power)
            bpm_axis = freqs * 60.0;
            set(h_fft_line, 'XData', bpm_axis, 'YData', power);

            if raw_bpm >= 45 && raw_bpm <= 180
                set(h_fft_peak, 'Value', raw_bpm, 'Visible', 'on');
            else
                set(h_fft_peak, 'Visible', 'off');
            end
        end

        drawnow limitrate;
    end
end
