classdef FaceTracker < handle
    % FACETRACKER Tracks human face and extracts spatial average RGB from physiological ROIs.
    %
    % Features:
    %   1. Automatic detection using Computer Vision Toolbox (if available) with
    %      robust fallback to Color-Based Skin Chrominance Segmentation for pure base MATLAB.
    %   2. Temporal smoothing with a 5-pixel deadband to freeze jitter when the subject is still.
    %   3. Persistence hold (30 frames) for transient blinks and micro-movements.
    %   4. Derivation of 4 microvascular anatomical ROIs:
    %      - Forehead (supratrochlear & supraorbital arteries)
    %      - Left & Right Cheeks (facial & transverse facial arteries)
    %      - Central Maxillary / Nose Bridge (angular artery)
    %   5. 10th-90th Percentile Luminance Trimming to reject hair, eyebrows, and specular glare.
    %
    % Course: Digital Signal Processing (Semester 5)

    properties
        smoothing_factor (1,1) double = 0.75
        smoothed_bbox (1,:) double = []        % [x, y, w, h]
        face_detected (1,1) logical = false
        frames_since_detection (1,1) double = 0
        has_vision_toolbox (1,1) logical = false
        cascade_detector = []
    end

    methods
        function obj = FaceTracker(smoothing_factor)
            if nargin >= 1
                obj.smoothing_factor = smoothing_factor;
            end
            
            % Check if Computer Vision Toolbox is available
            try
                if ~isempty(which('vision.CascadeObjectDetector'))
                    obj.cascade_detector = vision.CascadeObjectDetector('FrontalFaceCART');
                    obj.has_vision_toolbox = true;
                else
                    obj.has_vision_toolbox = false;
                end
            catch
                obj.has_vision_toolbox = false;
            end
        end

        function bbox = detect_face(obj, frame)
            % Detects face bounding box [x, y, w, h] in RGB frame.
            [H, W, ~] = size(frame);
            raw_bbox = [];

            % 1. Try Computer Vision Toolbox cascade detector if present
            if obj.has_vision_toolbox && ~isempty(obj.cascade_detector)
                try
                    bboxes = step(obj.cascade_detector, frame);
                    if ~isempty(bboxes)
                        % Pick largest face
                        areas = bboxes(:, 3) .* bboxes(:, 4);
                        [~, idx] = max(areas);
                        raw_bbox = double(bboxes(idx, :));
                    end
                catch
                    raw_bbox = [];
                end
            end

            % 2. Robust Skin Segmentation Fallback (Base MATLAB)
            if isempty(raw_bbox)
                raw_bbox = obj.detect_face_skin_fallback(frame);
            end

            % 3. Smoothing and deadband tracking
            if ~isempty(raw_bbox)
                obj.face_detected = true;
                obj.frames_since_detection = 0;
                bbox = obj.smooth_bbox(raw_bbox);
            else
                obj.frames_since_detection = obj.frames_since_detection + 1;
                if obj.frames_since_detection <= 30 && ~isempty(obj.smoothed_bbox)
                    obj.face_detected = true;
                    bbox = round(obj.smoothed_bbox);
                else
                    obj.face_detected = false;
                    obj.smoothed_bbox = [];
                    % Safe center fallback for continuous processing
                    cw = round(W * 0.40);
                    ch = round(H * 0.50);
                    cx = round((W - cw) / 2);
                    cy = round((H - ch) / 2);
                    bbox = [cx, cy, cw, ch];
                end
            end
        end

        function bbox = detect_face_skin_fallback(obj, frame)
            % Base MATLAB skin color segmentation in RGB / normalized color space.
            [H, W, ~] = size(frame);
            R = double(frame(:,:,1));
            G = double(frame(:,:,2));
            B = double(frame(:,:,3));

            % Rule-based human skin color segmentation
            skin_mask = (R > 75) & (G > 35) & (B > 20) & ...
                        ((max(max(R, G), B) - min(min(R, G), B)) > 15) & ...
                        (abs(R - G) > 12) & (R > G) & (R > B);

            % Focus on central-upper region where faces typically reside
            y_weight = repmat((1:H)', 1, W);
            central_mask = skin_mask & (y_weight > H * 0.10) & (y_weight < H * 0.85);

            [rows, cols] = find(central_mask);
            if length(rows) < 400
                bbox = [];
                return;
            end

            % Bounding coordinates from skin cluster
            min_r = max(1, quantile(rows, 0.05));
            max_r = min(H, quantile(rows, 0.95));
            min_c = max(1, quantile(cols, 0.05));
            max_c = min(W, quantile(cols, 0.95));

            bh = max_r - min_r;
            bw = max_c - min_c;

            if bh > 40 && bw > 40 && bh < H * 0.90 && bw < W * 0.90
                bbox = [min_c, min_r, bw, bh];
            else
                bbox = [];
            end
        end

        function bbox = smooth_bbox(obj, new_box)
            % Deadband filter: freezes bounding box when subject is stationary
            % to eliminate artificial high-frequency motion injection.
            x = new_box(1); y = new_box(2); w = new_box(3); h = new_box(4);

            if isempty(obj.smoothed_bbox)
                obj.smoothed_bbox = [x, y, w, h];
            else
                dx = abs(x - obj.smoothed_bbox(1));
                dy = abs(y - obj.smoothed_bbox(2));
                dw = abs(w - obj.smoothed_bbox(3));
                dh = abs(h - obj.smoothed_bbox(4));

                if dx < 5.0 && dy < 5.0 && dw < 5.0 && dh < 5.0
                    % Within deadband: keep current smoothed position
                else
                    a = obj.smoothing_factor;
                    obj.smoothed_bbox = a * obj.smoothed_bbox + (1.0 - a) * [x, y, w, h];
                end
            end
            bbox = round(obj.smoothed_bbox);
        end

        function rois = get_rois(obj, face_bbox, frame_size)
            % Derives physiological microvascular ROIs from face bounding box.
            max_h = frame_size(1);
            max_w = frame_size(2);
            fx = face_bbox(1); fy = face_bbox(2); fw = face_bbox(3); fh = face_bbox(4);

            clamp = @(rx, ry, rw, rh) [ ...
                max(1, min(round(rx), max_w - 1)), ...
                max(1, min(round(ry), max_h - 1)), ...
                max(2, min(round(rw), max_w - max(1, min(round(rx), max_w - 1)))), ...
                max(2, min(round(rh), max_h - max(1, min(round(ry), max_h - 1)))) ...
            ];

            rois.forehead    = clamp(fx + fw * 0.27, fy + fh * 0.15, fw * 0.46, fh * 0.17);
            rois.left_cheek  = clamp(fx + fw * 0.16, fy + fh * 0.50, fw * 0.22, fh * 0.18);
            rois.right_cheek = clamp(fx + fw * 0.62, fy + fh * 0.50, fw * 0.22, fh * 0.18);
            rois.central     = clamp(fx + fw * 0.38, fy + fh * 0.42, fw * 0.24, fh * 0.20);
        end

        function [mean_r, mean_g, mean_b] = extract_mean_rgb(obj, frame, rois, use_trimming)
            % Spatial averaging across all ROIs with 10th-90th percentile luminance trimming.
            if nargin < 4
                use_trimming = true;
            end

            total_r = 0.0;
            total_g = 0.0;
            total_b = 0.0;
            total_pixels = 0;

            roi_names = fieldnames(rois);
            for k = 1 : length(roi_names)
                rect = rois.(roi_names{k});
                rx = rect(1); ry = rect(2); rw = rect(3); rh = rect(4);

                roi_sub = frame(ry : ry + rh - 1, rx : rx + rw - 1, :);
                if isempty(roi_sub)
                    continue;
                end

                R_sub = double(roi_sub(:,:,1));
                G_sub = double(roi_sub(:,:,2));
                B_sub = double(roi_sub(:,:,3));

                if use_trimming
                    gray_sub = 0.2989 * R_sub + 0.5870 * G_sub + 0.1140 * B_sub;
                    p_low = quantile(gray_sub(:), 0.10);
                    p_high = quantile(gray_sub(:), 0.90);
                    valid_mask = (gray_sub >= p_low) & (gray_sub <= p_high);
                    n_valid = sum(valid_mask(:));

                    if n_valid > 15
                        total_r = total_r + sum(R_sub(valid_mask));
                        total_g = total_g + sum(G_sub(valid_mask));
                        total_b = total_b + sum(B_sub(valid_mask));
                        total_pixels = total_pixels + n_valid;
                        continue;
                    end
                end

                % Fallback: whole ROI averaging
                n_all = numel(R_sub);
                total_r = total_r + sum(R_sub(:));
                total_g = total_g + sum(G_sub(:));
                total_b = total_b + sum(B_sub(:));
                total_pixels = total_pixels + n_all;
            end

            if total_pixels == 0
                mean_r = 0.0; mean_g = 0.0; mean_b = 0.0;
            else
                mean_r = total_r / total_pixels;
                mean_g = total_g / total_pixels;
                mean_b = total_b / total_pixels;
            end
        end
    end
end
