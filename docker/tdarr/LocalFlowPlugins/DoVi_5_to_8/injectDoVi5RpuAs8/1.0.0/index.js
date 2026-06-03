"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g;
    return g = { next: verb(0), "throw": verb(1), "return": verb(2) }, typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.plugin = exports.details = void 0;
var cliUtils_1 = require("../../../../FlowHelpers/1.0.0/cliUtils");
var fileUtils_1 = require("../../../../FlowHelpers/1.0.0/fileUtils");

var details = function () { return ({
    name: 'Inject DoVi P5 RPU as Profile 8.1',
    description: 'Extracts the RPU from the original DoVi P5 source, converts it to Profile 8.1, '
        + 'then injects it into the re-encoded MKV produced by the Convert DoVi P5→P8 plugin.',
    style: {
        borderColor: 'orange',
    },
    tags: 'video',
    isStartPlugin: false,
    pType: '',
    requiresVersion: '2.11.01',
    sidebarPosition: -1,
    icon: '',
    inputs: [],
    outputs: [
        {
            number: 1,
            tooltip: 'Continue to next plugin',
        },
    ],
}); };
exports.details = details;

var plugin = function (args) { return __awaiter(void 0, void 0, void 0, function () {
    var lib, pluginWorkDir, baseName,
        p5HevcPath, p5AsP8HevcPath, rpuP8Path, p8RpuHevcPath, outputFilePath,
        videoStream, frameRate, shellCmd, cli, res;

    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                lib = require('../../../../../methods/lib')();
                args.inputs = lib.loadDefaultValues(args.inputs, details);

                pluginWorkDir = (0, fileUtils_1.getPluginWorkDir)(args);
                baseName = (0, fileUtils_1.getFileName)(args.originalLibraryFile._id);

                p5HevcPath    = pluginWorkDir + "/" + baseName + "_p5_raw.hevc";
                p5AsP8HevcPath = pluginWorkDir + "/" + baseName + "_p5_as_p8.hevc";
                rpuP8Path     = pluginWorkDir + "/" + baseName + "_rpu_p8.bin";
                p8RpuHevcPath = pluginWorkDir + "/" + baseName + "_p8_rpu.hevc";
                outputFilePath = pluginWorkDir + "/" + baseName + ".mkv";

                videoStream = (args.originalLibraryFile.ffProbeData.streams || []).find(function(s) { return s.codec_type === 'video'; });
                frameRate = (videoStream && videoStream.r_frame_rate) || '60000/1001';

                // Chain all 5 steps in a single shell command so only one CLI.runCli() call is
                // needed. Multiple sequential CLI.runCli() calls in one plugin trigger a bug in
                // Tdarr's cliUtils where updateWorker returns undefined and crashes the worker,
                // leaving files stuck in staged.
                //
                // Step 1: Demux P5 source MKV → raw Annex B HEVC (no hevc_mp4toannexb — MKV
                //         already uses Annex B; that filter is for MP4 containers only).
                // Step 2: dovi_tool -m 3 convert: rewrite RPU from P5 → P8.1 format.
                // Step 3: dovi_tool extract-rpu: pull the P8.1 RPU bin out.
                // Step 4: dovi_tool inject-rpu: inject P8.1 RPU into the re-encoded P8 HEVC.
                // Step 5: mkvmerge: mux P8 HEVC + audio/subs from original into final MKV.
                shellCmd = "ffmpeg -hide_banner -y"
                    + " -i \"" + args.originalLibraryFile._id + "\""
                    + " -c:v copy -an -f hevc"
                    + " \"" + p5HevcPath + "\""
                    + " && /usr/local/bin/dovi_tool -m 3 convert"
                    + " -i \"" + p5HevcPath + "\""
                    + " -o \"" + p5AsP8HevcPath + "\""
                    + " && /usr/local/bin/dovi_tool extract-rpu"
                    + " -i \"" + p5AsP8HevcPath + "\""
                    + " -o \"" + rpuP8Path + "\""
                    + " && /usr/local/bin/dovi_tool inject-rpu"
                    + " -i \"" + args.inputFileObj.file + "\""
                    + " --rpu-in \"" + rpuP8Path + "\""
                    + " -o \"" + p8RpuHevcPath + "\""
                    + " && mkvmerge"
                    + " -o \"" + outputFilePath + "\""
                    + " --default-duration \"0:" + frameRate + "fps\""
                    + " \"" + p8RpuHevcPath + "\""
                    + " --no-video \"" + args.originalLibraryFile._id + "\"";

                args.jobLog("Running: " + shellCmd);

                cli = new cliUtils_1.CLI({
                    cli: '/bin/sh',
                    spawnArgs: ['-c', shellCmd],
                    spawnOpts: {},
                    jobLog: args.jobLog,
                    outputFilePath: outputFilePath,
                    inputFileObj: args.inputFileObj,
                    logFullCliOutput: args.logFullCliOutput,
                    updateWorker: args.updateWorker,
                });
                return [4 /*yield*/, cli.runCli()];
            case 1:
                res = _a.sent();
                if (res.cliExitCode !== 0) {
                    args.jobLog('DoVi P5→P8 RPU inject pipeline failed');
                    throw new Error('DoVi P5→P8 inject pipeline failed');
                }

                args.logOutcome('tSuc');
                return [2 /*return*/, {
                    outputFileObj: { _id: outputFilePath },
                    outputNumber: 1,
                    variables: args.variables,
                }];
        }
    });
}); };
exports.plugin = plugin;
