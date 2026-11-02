function run_matlab(varargin)
    % RUN_MATLAB Root launcher for the MATLAB rPPG DSP Project.
    % Automatically adds the matlab/ folder to the MATLAB path and starts main.m.
    %
    % Usage:
    %   run_matlab                  % Opens interactive mode
    %   run_matlab('synthetic')     % Synthetic pulse generator (Default: 72 BPM)
    %   run_matlab('webcam')        % Live webcam
    %   run_matlab('test')          % Run unit test suite
    %   run_matlab('benchmark')     % Run benchmark and save dashboard figure

    root_dir = fileparts(mfilename('fullpath'));
    matlab_dir = fullfile(root_dir, 'matlab');
    if exist(matlab_dir, 'dir')
        addpath(matlab_dir);
    end

    main(varargin{:});
end
