function main(mode_arg, extra_arg)
    % MAIN Entry point for the MATLAB Remote Photoplethysmography (rPPG) System.
    %
    % Usage:
    %   main()                  % Interactive menu in MATLAB Command Window
    %   main('synthetic')       % Synthetic pulse generator (Default 72 BPM)
    %   main('synthetic', 85)   % Synthetic pulse generator at 85 BPM
    %   main('webcam')          % Live USB webcam feed
    %   main('video', 'my.mp4') % Offline video file playback
    %   main('test')            % Automated DSP unit tests
    %   main('benchmark')       % Verification benchmark and saves demo figure
    %
    % Course: Digital Signal Processing (Semester 5)

    clc;
    addpath(fileparts(mfilename('fullpath')));

    fprintf('========================================================================\n');
    fprintf('  REAL-TIME REMOTE PHOTOPLETHYSMOGRAPHY (rPPG) SYSTEM — MATLAB DSP     \n');
    fprintf('  Academic Course : Digital Signal Processing (Semester 5)              \n');
    fprintf('========================================================================\n\n');

    if nargin >= 1
        choice_str = lower(char(mode_arg));
        switch choice_str
            case {'synthetic', '1'}
                target_bpm = 72.0;
                if nargin >= 2 && isnumeric(extra_arg)
                    target_bpm = extra_arg;
                end
                rPPG_Dashboard('source', 'synthetic', 'bpm', target_bpm);
                return;
            case {'webcam', 'cam', '2'}
                rPPG_Dashboard('source', 'webcam');
                return;
            case {'video', 'file', '3'}
                if nargin >= 2 && (ischar(extra_arg) || isstring(extra_arg))
                    rPPG_Dashboard('source', char(extra_arg));
                else
                    [filename, pathname] = uigetfile({'*.mp4;*.avi;*.mov;*.mkv', 'Video Files (*.mp4, *.avi, *.mov)'}, 'Select Video File');
                    if isequal(filename, 0)
                        disp('No file selected. Exiting.');
                        return;
                    end
                    rPPG_Dashboard('source', fullfile(pathname, filename));
                end
                return;
            case {'test', 'tests', 'unit_test', '4'}
                test_dsp();
                return;
            case {'benchmark', 'verify', '5'}
                verify_synthetic();
                return;
        end
    end

    % Interactive Menu
    fprintf('Select Execution Mode:\n');
    fprintf('  [1] Launch Dashboard with Synthetic Pulse Generator (Default: 72 BPM)\n');
    fprintf('  [2] Launch Dashboard with Live USB Webcam Stream\n');
    fprintf('  [3] Launch Dashboard with Offline Video File\n');
    fprintf('  [4] Run Automated Mathematical DSP Test Suite (test_dsp)\n');
    fprintf('  [5] Run Benchmark Verification & Save Demo Figure (verify_synthetic)\n');
    fprintf('  [6] Exit\n\n');

    user_choice = input('Enter selection [1-6] (Default: 1): ', 's');
    if isempty(user_choice)
        user_choice = '1';
    end

    switch strtrim(user_choice)
        case '1'
            rPPG_Dashboard('source', 'synthetic', 'bpm', 72.0);
        case '2'
            rPPG_Dashboard('source', 'webcam');
        case '3'
            [filename, pathname] = uigetfile({'*.mp4;*.avi;*.mov;*.mkv', 'Video Files (*.mp4, *.avi, *.mov)'}, 'Select Video File');
            if isequal(filename, 0)
                disp('No file selected.');
                return;
            end
            rPPG_Dashboard('source', fullfile(pathname, filename));
        case '4'
            test_dsp();
        case '5'
            verify_synthetic();
        case '6'
            fprintf('Exiting rPPG System. Goodbye!\n');
        otherwise
            fprintf('Invalid selection. Starting synthetic mode by default...\n');
            rPPG_Dashboard('source', 'synthetic', 'bpm', 72.0);
    end
end
