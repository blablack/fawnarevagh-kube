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
        p5HevcPath, p5AsP8HevcPath, rpuP8Path, p8HevcPath, p8RpuHevcPath, outputFilePath,
        cli, res;
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                lib = require('../../../../../methods/lib')();
                args.inputs = lib.loadDefaultValues(args.inputs, details);

                pluginWorkDir = (0, fileUtils_1.getPluginWorkDir)(args);
                baseName = (0, fileUtils_1.getFileName)(args.originalLibraryFile._id);

                // dovi_tool only accepts raw Annex B HEVC streams.
                // The P5 source (MP4) and the re-encoded P8 MKV both need ffmpeg demux first.
                p5HevcPath    = pluginWorkDir + "/" + baseName + "_p5_raw.hevc";
                p5AsP8HevcPath = pluginWorkDir + "/" + baseName + "_p5_as_p8.hevc";
                rpuP8Path     = pluginWorkDir + "/" + baseName + "_rpu_p8.bin";
                p8HevcPath    = pluginWorkDir + "/" + baseName + "_p8_raw.hevc";
                p8RpuHevcPath = pluginWorkDir + "/" + baseName + "_p8_rpu.hevc";
                outputFilePath = pluginWorkDir + "/" + baseName + "_final_p8.mkv";

                // Step 1: Demux original P5 source → raw HEVC Annex B
                cli = new cliUtils_1.CLI({
                    cli: 'ffmpeg',
                    spawnArgs: [
                        '-hide_banner', '-y',
                        '-i', args.originalLibraryFile._id,
                        '-c:v', 'copy',
                        '-bsf:v', 'hevc_mp4toannexb',
                        '-an',
                        '-f', 'hevc',
                        p5HevcPath,
                    ],
                    spawnOpts: {},
                    jobLog: args.jobLog,
                    outputFilePath: p5HevcPath,
                    inputFileObj: args.inputFileObj,
                    logFullCliOutput: args.logFullCliOutput,
                    updateWorker: args.updateWorker,
                });
                return [4 /*yield*/, cli.runCli()];
            case 1:
                res = _a.sent();
                if (res.cliExitCode !== 0) {
                    args.jobLog('Failed to extract raw HEVC from original P5 source');
                    throw new Error('ffmpeg demux of P5 source failed');
                }

                // Step 2: Convert P5 HEVC → P8.1 HEVC (-m 3 is a global flag meaning "mode 3: P5→P8.1")
                cli = new cliUtils_1.CLI({
                    cli: '/usr/local/bin/dovi_tool',
                    spawnArgs: [
                        '-m', '3',
                        'convert',
                        '-i', p5HevcPath,
                        '-o', p5AsP8HevcPath,
                    ],
                    spawnOpts: {},
                    jobLog: args.jobLog,
                    outputFilePath: p5AsP8HevcPath,
                    inputFileObj: args.inputFileObj,
                    logFullCliOutput: args.logFullCliOutput,
                    updateWorker: args.updateWorker,
                });
                return [4 /*yield*/, cli.runCli()];
            case 2:
                res = _a.sent();
                if (res.cliExitCode !== 0) {
                    args.jobLog('Failed to convert P5 HEVC to P8.1');
                    throw new Error('dovi_tool convert P5→P8.1 failed');
                }

                // Step 3: Extract P8.1 RPU from the converted HEVC
                cli = new cliUtils_1.CLI({
                    cli: '/usr/local/bin/dovi_tool',
                    spawnArgs: [
                        'extract-rpu',
                        '-i', p5AsP8HevcPath,
                        '-o', rpuP8Path,
                    ],
                    spawnOpts: {},
                    jobLog: args.jobLog,
                    outputFilePath: rpuP8Path,
                    inputFileObj: args.inputFileObj,
                    logFullCliOutput: args.logFullCliOutput,
                    updateWorker: args.updateWorker,
                });
                return [4 /*yield*/, cli.runCli()];
            case 3:
                res = _a.sent();
                if (res.cliExitCode !== 0) {
                    args.jobLog('Failed to extract P8.1 RPU from converted HEVC');
                    throw new Error('dovi_tool extract-rpu (P8.1) failed');
                }

                // Step 4: Demux re-encoded P8 MKV → raw HEVC Annex B
                // MKV already stores HEVC in Annex B, no bitstream filter needed
                cli = new cliUtils_1.CLI({
                    cli: 'ffmpeg',
                    spawnArgs: [
                        '-hide_banner', '-y',
                        '-i', args.inputFileObj.file,
                        '-c:v', 'copy',
                        '-an',
                        '-f', 'hevc',
                        p8HevcPath,
                    ],
                    spawnOpts: {},
                    jobLog: args.jobLog,
                    outputFilePath: p8HevcPath,
                    inputFileObj: args.inputFileObj,
                    logFullCliOutput: args.logFullCliOutput,
                    updateWorker: args.updateWorker,
                });
                return [4 /*yield*/, cli.runCli()];
            case 4:
                res = _a.sent();
                if (res.cliExitCode !== 0) {
                    args.jobLog('Failed to extract raw HEVC from re-encoded P8 MKV');
                    throw new Error('ffmpeg demux of P8 MKV failed');
                }

                // Step 5: Inject P8.1 RPU into raw HEVC
                cli = new cliUtils_1.CLI({
                    cli: '/usr/local/bin/dovi_tool',
                    spawnArgs: [
                        'inject-rpu',
                        '-i', p8HevcPath,
                        '--rpu-in', rpuP8Path,
                        '-o', p8RpuHevcPath,
                    ],
                    spawnOpts: {},
                    jobLog: args.jobLog,
                    outputFilePath: p8RpuHevcPath,
                    inputFileObj: args.inputFileObj,
                    logFullCliOutput: args.logFullCliOutput,
                    updateWorker: args.updateWorker,
                });
                return [4 /*yield*/, cli.runCli()];
            case 5:
                res = _a.sent();
                if (res.cliExitCode !== 0) {
                    args.jobLog('Failed to inject P8.1 RPU into re-encoded HEVC');
                    throw new Error('dovi_tool inject-rpu failed');
                }

                // Step 6: Remux P8.1 HEVC + audio from the re-encoded MKV → final MKV
                // -map 1:a? is optional so it doesn't fail if the source had no audio.
                cli = new cliUtils_1.CLI({
                    cli: 'ffmpeg',
                    spawnArgs: [
                        '-hide_banner', '-y',
                        '-i', p8RpuHevcPath,
                        '-i', args.inputFileObj.file,
                        '-map', '0:v',
                        '-map', '1:a?',
                        '-c', 'copy',
                        outputFilePath,
                    ],
                    spawnOpts: {},
                    jobLog: args.jobLog,
                    outputFilePath: outputFilePath,
                    inputFileObj: args.inputFileObj,
                    logFullCliOutput: args.logFullCliOutput,
                    updateWorker: args.updateWorker,
                });
                return [4 /*yield*/, cli.runCli()];
            case 6:
                res = _a.sent();
                if (res.cliExitCode !== 0) {
                    args.jobLog('Failed to remux P8.1 HEVC + audio into final MKV');
                    throw new Error('ffmpeg final remux failed');
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
