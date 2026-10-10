'use strict';

const expectedHash = 'c823dda716e4584934a513c14c9757b18c9a62b89a8a81b0783085c799864bfb';
const receiveRva = 0x1b0985c;
let sequence = 0;
let setupStage = 'architecture';

try {
    if (Process.arch !== 'arm64' || Process.pointerSize !== 8) {
        throw new Error('unsupported-architecture');
    }
    setupStage = 'module';
    const module = Process.getModuleByName('libil2cpp.so');
    setupStage = 'library-read';
    const hash = Checksum.compute('sha256', File.readAllBytes(module.path));
    setupStage = 'library-hash';
    if (hash !== expectedHash) {
        throw new Error('artifact-mismatch');
    }
    setupStage = 'receive-address';
    const address = module.base.add(receiveRva);
    const range = Process.findRangeByAddress(address);
    if (receiveRva >= module.size || range === null || !range.protection.includes('x')) {
        throw new Error('invalid-receive-address');
    }
    setupStage = 'attach';
    Interceptor.attach(address, {
        onEnter(args) {
            const observedAt = Date.now();
            try {
                const array = args[2];
                const length = array.add(24).readU64().toNumber();
                if (length < 6 || length > 4 * 1024 * 1024) {
                    send({event: 'invalid-array'});
                    return;
                }
                const bytes = array.add(32).readByteArray(length);
                send({event: 'frame', sequence: ++sequence, observed_at_ms: observedAt}, bytes);
            } catch (_) {
                send({event: 'receive-error'});
            }
        }
    });
    send({event: 'ready'});
} catch (_) {
    send({event: 'setup-error', stage: setupStage});
}
