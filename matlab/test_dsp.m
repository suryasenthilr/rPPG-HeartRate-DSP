function test_dsp()
    % TEST_DSP Automated DSP Mathematical Verification Test Suite for MATLAB
    %
    % Validates:
    %   1. Linear Detrending & Moving Average Standardization
    %   2. 4th-Order Butterworth Filter Frequency Attenuation (Passband vs Stopband)
    %   3. Windowed Zero-Padded FFT Heart Rate Accuracy across 60, 72, 85, 110, 135 BPM (< 1.0 BPM error)
    %   4. CHROM Color Subspace Projection Method
    %
    % Course: Digital Signal Processing (Semester 5)

    fprintf('\n========================================================================\n');
    fprintf('  RUNNING rPPG DIGITAL SIGNAL PROCESSING (DSP) TEST SUITE (MATLAB)     \n');
    fprintf('========================================================================\n\n');

    pass_count = 0;
    total_tests = 0;

    %% Test 1: Detrending and Standardization
    total_tests = total_tests + 1;
    fprintf('[TEST 1/4] Detrending & Standardization ... ');
    try
        processor = RPPGSignalProcessor();
        fs = 30.0;
        t = linspace(0, 10, round(10 * fs));
        drift = 2.5 * t;
        pure_signal = sin(2 * pi * 1.2 * t);
        raw = drift + pure_signal;

        detrended = processor.detrend_signal(raw, fs);

        assert(abs(mean(detrended)) < 0.05, 'Mean after standardization must be ~0');
        assert(abs(std(detrended) - 1.0) < 0.05, 'Std after standardization must be ~1');

        corr_mat = corrcoef(detrended, pure_signal);
        corr = corr_mat(1, 2);
        assert(corr > 0.85, sprintf('Correlation %f must be > 0.85', corr));

        fprintf('PASSED (corr = %.3f, mean = %.4f, std = %.4f)\n', corr, mean(detrended), std(detrended));
        pass_count = pass_count + 1;
    catch ME
        fprintf('FAILED: %s\n', ME.message);
    end

    %% Test 2: Butterworth Filter Attenuation
    total_tests = total_tests + 1;
    fprintf('[TEST 2/4] 4th-Order Butterworth Passband Preservation & Attenuation ... ');
    try
        processor = RPPGSignalProcessor('low_bpm', 45.0, 'high_bpm', 150.0);
        fs = 30.0;
        t = linspace(0, 10, round(10 * fs));

        % Frequencies: 0.2 Hz (drift), 1.25 Hz (cardiac), 8.0 Hz (noise)
        f_low = 0.2;
        f_pass = 1.25;
        f_high = 8.0;

        sig_low = sin(2 * pi * f_low * t);
        sig_pass = sin(2 * pi * f_pass * t);
        sig_high = sin(2 * pi * f_high * t);

        composite = sig_low + sig_pass + sig_high;
        filtered = processor.butterworth_bandpass_filter(composite, fs);

        fft_in = abs(fft(composite)).^2;
        fft_out = abs(fft(filtered)).^2;
        N = length(composite);
        freqs = (0 : floor(N/2)) * (fs / N);

        [~, idx_pass] = min(abs(freqs - f_pass));
        [~, idx_low]  = min(abs(freqs - f_low));
        [~, idx_high] = min(abs(freqs - f_high));

        gain_pass = fft_out(idx_pass) / fft_in(idx_pass);
        gain_low  = fft_out(idx_low) / fft_in(idx_low);
        gain_high = fft_out(idx_high) / fft_in(idx_high);

        assert(gain_pass > 0.50, sprintf('Passband gain too low: %.3f', gain_pass));
        assert(gain_low < 0.15, sprintf('Low-freq stopband gain too high: %.3f', gain_low));
        assert(gain_high < 0.05, sprintf('High-freq stopband gain too high: %.3f', gain_high));

        fprintf('PASSED (Passband Gain = %.2f, Low Stopband = %.3f, High Stopband = %.4f)\n', ...
            gain_pass, gain_low, gain_high);
        pass_count = pass_count + 1;
    catch ME
        fprintf('FAILED: %s\n', ME.message);
    end

    %% Test 3: Zero-Padded Windowed FFT Accuracy across BPM Range
    target_bpms = [60.0, 72.0, 85.0, 110.0, 135.0];
    fprintf('[TEST 3/4] Multi-Rate FFT Heart Rate Accuracy (< 1.0 BPM error):\n');
    all_bpm_passed = true;

    for k = 1 : length(target_bpms)
        total_tests = total_tests + 1;
        target_bpm = target_bpms(k);
        try
            processor = RPPGSignalProcessor('buffer_size', 300);
            fs = 30.0;
            f_cardiac = target_bpm / 60.0;
            n_samples = 250;
            t = (0 : n_samples - 1) / fs;

            noise = randn(1, n_samples) * 0.05;
            g_signal = 150.0 + 1.5 * sin(2 * pi * f_cardiac * t) + noise;
            r_signal = 180.0 + 0.5 * sin(2 * pi * f_cardiac * t);
            b_signal = 120.0 + 0.2 * sin(2 * pi * f_cardiac * t);

            for i = 1 : n_samples
                processor.add_sample(r_signal(i), g_signal(i), b_signal(i), t(i));
            end

            [~, raw_bpm, conf, ~, ~, ~] = processor.process();
            err = abs(raw_bpm - target_bpm);

            assert(err <= 1.0, sprintf('Target %.1f BPM got %.1f BPM (Error: %.2f BPM)', target_bpm, raw_bpm, err));
            fprintf('   -> Target: %5.1f BPM | Measured: %5.1f BPM | Error: %4.2f BPM | Conf: %.2f [PASS]\n', ...
                target_bpm, raw_bpm, err, conf);
            pass_count = pass_count + 1;
        catch ME
            fprintf('   -> Target: %5.1f BPM | FAILED: %s\n', target_bpm, ME.message);
            all_bpm_passed = false;
        end
    end

    %% Test 4: CHROM Subspace Extraction Mode
    total_tests = total_tests + 1;
    fprintf('[TEST 4/4] CHROM Subspace Projection Method ... ');
    try
        chrom_proc = RPPGSignalProcessor('method', 'chrom');
        fs = 30.0;
        n_samples = 250;
        t = (0 : n_samples - 1) / fs;
        f_cardiac = 75.0 / 60.0;

        % Optical reflectance modulation with motion-correlated illumination shifts
        motion_shift = 15.0 * sin(2 * pi * 0.4 * t);
        g_sig = 150.0 + 1.2 * sin(2 * pi * f_cardiac * t) + motion_shift;
        r_sig = 180.0 + 0.6 * sin(2 * pi * f_cardiac * t) + motion_shift;
        b_sig = 120.0 + 0.3 * sin(2 * pi * f_cardiac * t) + motion_shift;

        for i = 1 : n_samples
            chrom_proc.add_sample(r_sig(i), g_sig(i), b_sig(i), t(i));
        end

        [bpm_chrom, ~, conf_chrom, ~, ~, ~] = chrom_proc.process();
        err = abs(bpm_chrom - 75.0);

        assert(err <= 2.0, sprintf('CHROM mode target 75 BPM got %.1f BPM (Error: %.2f BPM)', bpm_chrom, err));
        fprintf('PASSED (Target: 75.0 BPM, CHROM Measured: %.1f BPM, Confidence: %.2f)\n', bpm_chrom, conf_chrom);
        pass_count = pass_count + 1;
    catch ME
        fprintf('FAILED: %s\n', ME.message);
    end

    %% Summary
    fprintf('\n------------------------------------------------------------------------\n');
    fprintf('  TEST RESULTS: %d / %d PASSED (%.1f%%)\n', pass_count, total_tests, (pass_count / total_tests) * 100);
    fprintf('========================================================================\n\n');
end
