const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');

function init(context) {
    const portFilePath = path.join(__dirname, 'port.txt');
    // Create local server to listen for ESLifier's request to export Vortex's Redux store state
    const server = http.createServer((req, res) => {
        if (req.method === 'GET' && req.url === '/export-state') {
            try {
                const state = context.api.store.getState();
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify(state));
            } catch (err) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: err.message }));
            }
        } else {
            res.writeHead(404);
            res.end();
        }
    });
    // Save port number so ESLifier knows where to connect to
    server.listen(0, '127.0.0.1', () => {
        const assignedPort = server.address().port;
        try {
            fs.writeFileSync(portFilePath, assignedPort.toString(), 'utf-8');
        } catch (err) {
            console.error("Failed to write port file", err);
        }
    });

    // Delete port number file and close server on unload
    window.addEventListener('beforeunload', () => {
        try {
            if (fs.existsSync(portFilePath)) {
                fs.unlinkSync(portFilePath);
            }
            server.close();
        } catch (err) {
            console.error("Failed to delete port file on exit", err);
        }
    });
}

exports.default = init;