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
    name: 'Convert DoVi Profile 5 to Profile 8',
    description: 'Re-encode DoVi Profile 5 to Profile 8 using libplacebo + hevc_qsv (Intel Quick Sync). '
        + 'Applies Dolby Vision tone mapping via libplacebo, uploads frames to QSV, and outputs an MKV with Main 10 profile.',
    style: {
        borderColor: 'orange',
    },
    tags: 'video',
    isStartPlugin: false,
    pType: '',
    requiresVersion: '2.11.01',
    sidebarPosition: -1,
    icon: '',
    inputs: [
        {
            label: 'QSV Preset',
            name: 'preset',
            type: 'string',
            defaultValue: 'medium',
            inputUI: {
                type: 'dropdown',
                options: ['veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'],
            },
            tooltip: 'hevc_qsv encoding preset — slower = better quality/compression (default: medium)',
        },
        {
            label: 'Global Quality',
            name: 'crf',
            type: 'number',
            defaultValue: '20',
            inputUI: { type: 'text' },
            tooltip: 'hevc_qsv global_quality — lower = better quality, larger file (default: 20, range 1-51)',
        },
    ],
    outputs: [
        {
            number: 1,
            tooltip: 'Continue to next plugin',
        },
    ],
}); };
exports.details = details;

var plugin = function (args) { return __awaiter(void 0, void 0, void 0, function () {
    var lib, videoStream, width, height, preset, crf, pluginWorkDir, baseName, outputFilePath, vf, shellCmd, cli, res;
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                lib = require('../../../../../methods/lib')();
                args.inputs = lib.loadDefaultValues(args.inputs, details);

                videoStream = args.inputFileObj.ffProbeData.streams.find(function (s) { return s.codec_type === 'video'; });
                if (!videoStream) {
                    throw new Error('No video stream found in input file');
                }
                width = String(videoStream.width);
                height = String(videoStream.height);
                preset = String(args.inputs.preset || 'medium');
                crf = String(args.inputs.crf || '20');

                pluginWorkDir = (0, fileUtils_1.getPluginWorkDir)(args);
                baseName = (0, fileUtils_1.getFileName)(args.originalLibraryFile._id);
                outputFilePath = pluginWorkDir + "/" + baseName + "_profile8.hevc";

                vf = "libplacebo=w=" + width + ":h=" + height
                    + ":format=p010:colorspace=bt2020nc:color_primaries=bt2020"
                    + ":color_trc=smpte2084:apply_dolbyvision=true"
                    + ",hwupload=extra_hw_frames=64";

                shellCmd = "ffmpeg -hide_banner -y"
                    + " -init_hw_device qsv=hw:/dev/dri/renderD128"
                    + " -i \"" + args.inputFileObj.file + "\""
                    + " -vf \"" + vf + "\""
                    + " -c:v hevc_qsv"
                    + " -profile:v main10"
                    + " -preset " + preset
                    + " -global_quality " + crf
                    + " -an"
                    + " \"" + outputFilePath + "\"";

                args.jobLog("Running: " + shellCmd);

                cli = new cliUtils_1.CLI({
                    cli: 'ffmpeg',
                    spawnArgs: [
                        '-hide_banner', '-y',
                        '-init_hw_device', 'qsv=hw:/dev/dri/renderD128',
                        '-i', args.inputFileObj.file,
                        '-vf', vf,
                        '-c:v', 'hevc_qsv',
                        '-profile:v', 'main10',
                        '-preset', preset,
                        '-global_quality', crf,
                        '-an',
                        outputFilePath,
                    ],
                    spawnOpts: {},
                    jobLog: args.jobLog,
                    outputFilePath: outputFilePath,
                    inputFileObj: args.inputFileObj,
                    logFullCliOutput: args.logFullCliOutput,
                    updateWorker: args.updateWorker,
                    args: args,
                });

                return [4 /*yield*/, cli.runCli()];
            case 1:
                res = _a.sent();
                if (res.cliExitCode !== 0) {
                    args.jobLog('ffmpeg DoVi P5 -> P8 conversion failed');
                    throw new Error('ffmpeg failed');
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
