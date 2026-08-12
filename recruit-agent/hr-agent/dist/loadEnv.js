"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
/** 轻量加载 .env（无需 dotenv 依赖） */
function loadEnv(file = path_1.default.join(process.cwd(), '.env')) {
    try {
        if (!fs_1.default.existsSync(file))
            return;
        const text = fs_1.default.readFileSync(file, 'utf8');
        for (const line of text.split(/\r?\n/)) {
            const t = line.trim();
            if (!t || t.startsWith('#'))
                continue;
            const i = t.indexOf('=');
            if (i <= 0)
                continue;
            const key = t.slice(0, i).trim();
            let val = t.slice(i + 1).trim();
            if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
                val = val.slice(1, -1);
            }
            if (process.env[key] === undefined)
                process.env[key] = val;
        }
    }
    catch {
        /* ignore */
    }
}
loadEnv();
