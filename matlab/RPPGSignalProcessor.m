classdef RPPGSignalProcessor < handle
    % RPPGSIGNALPROCESSOR Digital Signal Processor for real-time Remote Photoplethysmography (rPPG).
    %
    % Implements:
    %   1. Signal Buffering & Timestamp Management
    %   2. Temporal Sliding Window Pruning (7.5-second duration)
    %   3. Green Channel & CHROM Multi-Channel Subspace Extraction
    %   4. Linear Detrending & Moving Average Baseline Removal
    %   5. 4th-Order Zero-Phase Butterworth Bandpass Filtering (0.75 - 3.0 Hz)
    %   6. Zero-Padded Windowed Fast Fourier Transform (FFT, N=2048)
    %   7. Recursive Spectral Density Averaging & Continuity Peak Tracking
    %   8. Spectral Energy SNR (dB) & Multi-Tier Confidence Scoring
    %   9. Dynamic Exponential Moving Average (EMA) with Persistence Hold
    %
    % Course: Digital Signal Processing (Semester 5)
    
    properties
        buffer_size (1,1) double = 250
        min_freq (1,1) double = 45.0 / 60.0    % ~0.75 Hz (45 BPM)
        max_freq (1,1) double = 180.0 / 60.0   % ~3.00 Hz (180 BPM)
        method (1,:) char = 'green'            % 'green' or 'chrom'
        
        % Buffers for spatial mean signals and arrival timestamps
        raw_r (1,:) double = []
        raw_g (1,:) double = []
        raw_b (1,:) double = []
        timestamps (1,:) double = []
        
        % Smoothed pipeline state
        smooth_bpm (1,1) double = 0.0
        bpm_history (1,:) double = []
        snr (1,1) double = 0.0
        confidence (1,1) double = 0.0
        hold_frames (1,1) double = 0
        smooth_power (1,:) double = []
    end
    
    methods
        function obj = RPPGSignalProcessor(varargin)
            % Constructor: RPPGSignalProcessor('buffer_size', 250, 'low_bpm', 45, 'high_bpm', 180, 'method', 'green')
            p = inputParser;
            addParameter(p, 'buffer_size', 250, @isnumeric);
            addParameter(p, 'low_bpm', 45.0, @isnumeric);
            addParameter(p, 'high_bpm', 180.0, @isnumeric);
            addParameter(p, 'method', 'green', @ischar);
            parse(p, varargin{:});
            
            obj.buffer_size = p.Results.buffer_size;
            obj.min_freq = p.Results.low_bpm / 60.0;
            obj.max_freq = p.Results.high_bpm / 60.0;
            obj.method = lower(p.Results.method);
            obj.reset();
        end
        
        function reset(obj)
            % Clears all signal buffers and resets filter state
            obj.raw_r = [];
            obj.raw_g = [];
            obj.raw_b = [];
            obj.timestamps = [];
            obj.bpm_history = [];
            obj.smooth_bpm = 0.0;
            obj.snr = 0.0;
            obj.confidence = 0.0;
            obj.hold_frames = 0;
            obj.smooth_power = [];
        end
        
        function add_sample(obj, r, g, b, timestamp)
            % Appends spatial average RGB values and frame arrival timestamp.
            % Enforces a 7.5-second temporal duration window to prevent motion trapping.
            obj.raw_r(end + 1) = double(r);
            obj.raw_g(end + 1) = double(g);
            obj.raw_b(end + 1) = double(b);
            obj.timestamps(end + 1) = double(timestamp);
            
            % Enforce temporal sliding window (7.5 seconds)
            while length(obj.timestamps) > 40 && (obj.timestamps(end) - obj.timestamps(1) > 7.5)
                obj.raw_r(1) = [];
                obj.raw_g(1) = [];
                obj.raw_b(1) = [];
                obj.timestamps(1) = [];
            end
            
            % Enforce maximum sample buffer size
            if length(obj.timestamps) > obj.buffer_size
                n_excess = length(obj.timestamps) - obj.buffer_size;
                obj.raw_r(1:n_excess) = [];
                obj.raw_g(1:n_excess) = [];
                obj.raw_b(1:n_excess) = [];
                obj.timestamps(1:n_excess) = [];
            end
        end
        
        function fs = estimate_sampling_rate(obj)
            % Calculates empirical frame rate across the stored buffer.
            % Using total duration (t_last - t_first) eliminates frame-to-frame timestamp jitter.
            n = length(obj.timestamps);
            if n < 5
                fs = 30.0;
                return;
            end
            total_time = obj.timestamps(end) - obj.timestamps(1);
            if total_time <= 0.1
                fs = 30.0;
                return;
            end
            measured_fs = (n - 1) / total_time;
            fs = min(max(measured_fs, 15.0), 60.0);
        end
        
        function pulse = extract_raw_pulse(obj)
            % Extracts raw pulse signal from RGB buffers based on selected method:
            %   - 'green': -G(t) / L(t) where L(t) = (R+G+B)/3
            %   - 'chrom': Chrominance-based method (de Haan & Jeanne, 2013)
            r = obj.raw_r;
            g = obj.raw_g;
            b = obj.raw_b;
            
            % Total spatial luminance normalization cancels webcam auto-exposure and AC flicker
            luminance = (r + g + b) / 3.0 + 1e-6;
            rn = r ./ luminance;
            gn = g ./ luminance;
            bn = b ./ luminance;
            
            if strcmpi(obj.method, 'chrom')
                % 3D-to-1D Subspace projection
                xs = 3.0 * rn - 2.0 * gn;
                ys = 1.5 * rn + gn - 1.5 * bn;
                
                std_xs = std(xs);
                std_ys = std(ys);
                
                if std_ys > 1e-6
                    alpha = std_xs / std_ys;
                    pulse = xs - alpha * ys;
                else
                    pulse = xs;
                end
            else
                % Normalized Green channel:
                % Inverted (-gn) so systolic blood volume expansion appears as an upward peak
                pulse = -gn;
            end
        end
        
        function detrended = detrend_signal(obj, signal, fs)
            % Removes baseline drift and low-frequency motion artifacts.
            % Combines linear detrending with moving average subtraction.
            
            % Step 1: Linear detrending
            detrended = detrend(signal, 'linear');
            
            % Step 2: Moving average high-pass (~2.0 seconds cutoff ~0.5 Hz)
            win_size = max(7, round(fs * 2.0));
            if mod(win_size, 2) == 0
                win_size = win_size + 1;
            end
            
            if length(detrended) > win_size
                % Pad edges with nearest values to prevent boundary ringing
                half_w = floor(win_size / 2);
                padded = [repmat(detrended(1), 1, half_w), detrended, repmat(detrended(end), 1, half_w)];
                kernel = ones(1, win_size) / win_size;
                baseline_full = conv(padded, kernel, 'same');
                baseline = baseline_full(half_w + 1 : end - half_w);
                detrended = detrended - baseline;
            end
            
            % Step 3: Zero-mean unit-variance standardization
            s_std = std(detrended);
            if s_std > 1e-6
                detrended = (detrended - mean(detrended)) / s_std;
            end
        end
        
        function filtered = butterworth_bandpass_filter(obj, signal, fs, order)
            % Applies a zero-phase 4th-order digital Butterworth bandpass filter.
            % Uses filtfilt for 0 deg phase distortion.
            if nargin < 4
                order = 2; % 2nd-order with filtfilt yields effective 4th-order response
            end
            
            nyquist = 0.5 * fs;
            low = obj.min_freq / nyquist;
            high = obj.max_freq / nyquist;
            
            % Guard against invalid normalized frequency bounds
            low = max(0.01, min(low, 0.95));
            high = max(low + 0.05, min(high, 0.99));
            
            [b, a] = butter(order, [low, high], 'bandpass');
            
            % Zero-phase filtering if signal is sufficiently long
            if length(signal) > 3 * (2 * order + 1)
                filtered = filtfilt(b, a, signal);
            else
                filtered = filter(b, a, signal);
            end
        end
        
        function [freqs, normalized_power] = compute_fft(obj, signal, fs, n_fft)
            % Computes windowed Fast Fourier Transform (FFT) with zero-padding.
            if nargin < 4
                n_fft = 2048;
            end
            
            n_samples = length(signal);
            % Hanning window to suppress spectral leakage sidelobes to -31.5 dB
            n_idx = (0 : n_samples - 1)';
            window = 0.5 * (1 - cos(2 * pi * n_idx / max(1, n_samples - 1)))';
            windowed_signal = signal .* window;
            
            % Zero-padding for fine frequency resolution (< 1 BPM per bin)
            n_points = max(n_fft, 2^(ceil(log2(n_samples)) + 1));
            Y = fft(windowed_signal, n_points);
            
            n_half = floor(n_points / 2) + 1;
            freqs = (0 : n_half - 1) * (fs / n_points);
            
            power = abs(Y(1 : n_half)).^2;
            max_power = max(power);
            if max_power > 0
                normalized_power = power / max_power;
            else
                normalized_power = power;
            end
        end
        
        function [raw_bpm, snr_db, conf] = extract_bpm_and_snr(obj, freqs, power)
            % Identifies the dominant cardiac frequency in physiological passband.
            valid_mask = (freqs >= obj.min_freq) & (freqs <= obj.max_freq);
            valid_freqs = freqs(valid_mask);
            valid_power = power(valid_mask);
            
            if isempty(valid_power)
                raw_bpm = 0.0;
                snr_db = 0.0;
                conf = 0.0;
                return;
            end
            
            % Local peak detection separated by at least ~6 BPM (0.10 Hz)
            freq_step = 0.015;
            if length(freqs) > 1
                freq_step = freqs(2) - freqs(1);
            end
            min_dist = max(1, round(0.10 / freq_step));
            
            % Robust local maxima search
            n_valid = length(valid_power);
            peak_indices = [];
            for i = 2 : n_valid - 1
                if valid_power(i) > valid_power(i-1) && valid_power(i) >= valid_power(i+1)
                    if isempty(peak_indices) || (i - peak_indices(end) >= min_dist)
                        peak_indices(end + 1) = i; %#ok<AGROW>
                    elseif valid_power(i) > valid_power(peak_indices(end))
                        peak_indices(end) = i;
                    end
                end
            end
            
            % Interior search away from respiratory edge leakage (0.82 to 2.80 Hz = 50 to 168 BPM)
            interior_mask = (valid_freqs >= 0.82) & (valid_freqs <= 2.80);
            interior_indices = find(interior_mask);
            
            if ~isempty(interior_indices)
                search_indices = intersect(peak_indices, interior_indices);
                if isempty(search_indices)
                    [~, max_rel_idx] = max(valid_power(interior_indices));
                    peak_idx = interior_indices(max_rel_idx);
                else
                    if obj.smooth_bpm > 0 && length(obj.bpm_history) >= 3
                        prev_freq = obj.smooth_bpm / 60.0;
                        scores = zeros(size(search_indices));
                        for k = 1 : length(search_indices)
                            p_i = search_indices(k);
                            f = valid_freqs(p_i);
                            p = valid_power(p_i);
                            continuity_weight = exp(-((f - prev_freq)^2) / (2.0 * (0.35^2)));
                            scores(k) = p * (0.35 + 0.65 * continuity_weight);
                        end
                        [~, best_k] = max(scores);
                        peak_idx = search_indices(best_k);
                    else
                        [~, best_k] = max(valid_power(search_indices));
                        peak_idx = search_indices(best_k);
                    end
                end
            else
                [~, peak_idx] = max(valid_power);
            end
            
            peak_freq = valid_freqs(peak_idx);
            raw_bpm = peak_freq * 60.0;
            
            % Peak band: peak_freq +/- 0.12 Hz (~7.2 BPM window around peak)
            peak_band = 0.12;
            signal_mask = abs(valid_freqs - peak_freq) <= peak_band;
            signal_power = sum(valid_power(signal_mask));
            total_power = sum(valid_power) + 1e-8;
            noise_power = max(total_power - signal_power, 1e-8);
            
            % Spectral energy concentration ratio in peak
            concentration = signal_power / total_power;
            snr_linear = signal_power / noise_power;
            snr_db = 10.0 * log10(max(snr_linear, 1e-3));
            
            % Continuous confidence mapping: diffuse noise ~ 0.18, clean peak >= 0.40
            conf = min(max((concentration - 0.18) / 0.35, 0.05), 1.0);
        end
        
        function [smooth_bpm, raw_bpm, confidence, filtered_pulse, freqs, smooth_power] = process(obj)
            % Executes full DSP pipeline on currently buffered samples.
            smooth_bpm = 0.0;
            raw_bpm = 0.0;
            confidence = 0.0;
            filtered_pulse = [];
            freqs = [];
            smooth_power = [];
            
            n_samples = length(obj.raw_g);
            % Need at least ~50 frames for reliable estimation
            if n_samples < 50
                return;
            end
            
            fs = obj.estimate_sampling_rate();
            if fs < 10.0
                return;
            end
            
            % 1. Multi-channel signal extraction
            raw_signal = obj.extract_raw_pulse();
            
            % 2. Linear & moving average detrending
            detrended = obj.detrend_signal(raw_signal, fs);
            
            % 3. 4th-order Butterworth bandpass filtering
            filtered_pulse = obj.butterworth_bandpass_filter(detrended, fs);
            
            % 4. Zero-padded windowed FFT
            [freqs, power] = obj.compute_fft(filtered_pulse, fs, 2048);
            
            % 5. Temporal recursive spectral power averaging
            if isempty(obj.smooth_power) || length(obj.smooth_power) ~= length(power)
                obj.smooth_power = power;
            else
                obj.smooth_power = 0.85 * obj.smooth_power + 0.15 * power;
            end
            
            % Normalize smoothed spectrum
            max_sp = max(obj.smooth_power);
            if max_sp > 0
                obj.smooth_power = obj.smooth_power / max_sp;
            end
            smooth_power = obj.smooth_power;
            
            % 6. Peak detection & SNR calculation
            [raw_bpm, snr_db, conf] = obj.extract_bpm_and_snr(freqs, obj.smooth_power);
            if obj.snr == 0.0
                obj.snr = snr_db;
            else
                obj.snr = 0.94 * obj.snr + 0.06 * snr_db;
            end
            
            % 7. Rate stability continuity metric
            if obj.smooth_bpm > 0 && length(obj.bpm_history) >= 3
                bpm_diff = abs(raw_bpm - obj.smooth_bpm);
                stability = exp(-(bpm_diff^2) / (2.0 * (12.0^2)));
                conf_combined = min(max(0.60 * conf + 0.40 * stability, 0.05), 0.95);
            else
                conf_combined = min(max(conf, 0.05), 0.90);
            end
            
            % Temporal confidence smoothing
            if obj.confidence <= 0.05
                obj.confidence = conf_combined;
            else
                obj.confidence = 0.96 * obj.confidence + 0.04 * conf_combined;
            end
            confidence = obj.confidence;
            
            % 8. Dynamic Exponential Moving Average (EMA) with Persistence Hold
            if raw_bpm > 0
                if conf_combined >= 0.25
                    if obj.smooth_bpm == 0.0
                        obj.smooth_bpm = raw_bpm;
                    else
                        alpha = 0.10 * conf_combined + 0.03;
                        if abs(raw_bpm - obj.smooth_bpm) < 20.0 || length(obj.bpm_history) < 5
                            obj.smooth_bpm = alpha * raw_bpm + (1.0 - alpha) * obj.smooth_bpm;
                        else
                            obj.smooth_bpm = 0.03 * raw_bpm + 0.97 * obj.smooth_bpm;
                        end
                    end
                    obj.bpm_history(end + 1) = raw_bpm;
                    if length(obj.bpm_history) > 30
                        obj.bpm_history(1) = [];
                    end
                    obj.hold_frames = 90; % Hold for ~3s of transient noise
                else
                    if obj.hold_frames > 0
                        obj.hold_frames = obj.hold_frames - 1;
                    else
                        if length(obj.bpm_history) >= 5
                            obj.smooth_bpm = median(obj.bpm_history);
                        end
                    end
                end
            end
            
            smooth_bpm = obj.smooth_bpm;
        end
    end
end
