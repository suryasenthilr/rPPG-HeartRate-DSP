classdef SyntheticPulseGenerator < handle
    % SYNTHETICPULSEGENERATOR Generates a synthetic facial video stream with microvascular
    % pulsatile color variations for automated DSP benchmarking and hardware-independent testing.
    %
    % Course: Digital Signal Processing (Semester 5)

    properties
        target_bpm (1,1) double = 72.0
        fps (1,1) double = 30.0
        frame_idx (1,1) double = 0
        pulse_freq (1,1) double = 1.20   % Hz
        start_time (1,1) double = 0
    end

    methods
        function obj = SyntheticPulseGenerator(target_bpm, fps)
            if nargin >= 1
                obj.target_bpm = target_bpm;
            end
            if nargin >= 2
                obj.fps = fps;
            end
            obj.pulse_freq = obj.target_bpm / 60.0;
            obj.frame_idx = 0;
            obj.start_time = tic;
        end

        function reset(obj, new_bpm)
            if nargin >= 2
                obj.target_bpm = new_bpm;
                obj.pulse_freq = new_bpm / 60.0;
            end
            obj.frame_idx = 0;
            obj.start_time = tic;
        end

        function [success, frame, timestamp] = read(obj)
            % Generates next synthetic 480x640 RGB frame with modulated pulse
            t = obj.frame_idx / obj.fps;
            obj.frame_idx = obj.frame_idx + 1;
            timestamp = t;

            H = 480;
            W = 640;

            % Dark background
            frame = zeros(H, W, 3, 'uint8');
            frame(:,:,1) = 35;
            frame(:,:,2) = 30;
            frame(:,:,3) = 30;

            % Synthetic face oval
            cx = 320;
            cy = 240;
            rx = 110;
            ry = 150;

            [X, Y] = meshgrid(1:W, 1:H);
            ellipse_mask = (((X - cx) / rx).^2 + ((Y - cy) / ry).^2) <= 1.0;

            % Microvascular BVP modulation:
            % Systolic pulse amplitude ~ 1.5% modulation on green channel
            pulse_mod = 1.0 + 0.015 * sin(2 * pi * obj.pulse_freq * t);
            % Slight respiratory baseline wander (0.25 Hz)
            drift = 0.005 * sin(2 * pi * 0.25 * t);
            % High-frequency thermal camera sensor noise
            sensor_noise = randn() * 0.002;

            g_val = uint8(min(max(round(160.0 * (pulse_mod + drift + sensor_noise)), 0), 255));
            r_val = uint8(205);
            b_val = uint8(130);

            % Fill face skin region
            R_ch = frame(:,:,1);
            G_ch = frame(:,:,2);
            B_ch = frame(:,:,3);

            R_ch(ellipse_mask) = r_val;
            G_ch(ellipse_mask) = g_val;
            B_ch(ellipse_mask) = b_val;

            % Draw synthetic facial features (eyes and mouth) for detection
            % Left Eye
            eye_l = ((X - 280).^2 + (Y - 210).^2) <= 12^2;
            % Right Eye
            eye_r = ((X - 360).^2 + (Y - 210).^2) <= 12^2;
            % Mouth
            mouth = (((X - 320) / 32).^2 + ((Y - 290) / 10).^2) <= 1.0 & (Y >= 290);

            feat_mask = eye_l | eye_r | mouth;
            R_ch(feat_mask) = 50;
            G_ch(feat_mask) = 45;
            B_ch(feat_mask) = 45;

            frame(:,:,1) = R_ch;
            frame(:,:,2) = G_ch;
            frame(:,:,3) = B_ch;

            success = true;
        end
    end
end
