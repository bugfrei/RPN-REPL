#!/usr/bin/env node
const { spawn } = require("child_process");
const readline = require("readline");

const TARGET = require("path").resolve(__dirname, "rpn.js"); // anpassen, falls nötig
let last = "";                       // merkt den letzten Wert
const history = [];                  // einfache History im Speicher

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  historySize: 1000
});

function promptWithDefault() {
  rl.setPrompt("Parameter: ");
  rl.prompt();
  if (last) rl.write(last); // prefilling
}

rl.on("line", (line) => {
  const arg = line.trim();
  if (arg.length) {
    last = arg;
    history.unshift(arg);
    // History für ↑ nutzbar machen (rl.history ist eine Stack-ähnliche Liste)
    rl.history = [...history];
  }

  // Kindprozess starten und Ausgaben direkt durchreichen
  const child = spawn(process.execPath, [TARGET, arg], { stdio: "inherit" });

  child.on("exit", () => {
    promptWithDefault();
  });
});

rl.on("SIGINT", () => {
  rl.close();
});

rl.on("close", () => {
  process.exit(0);
});

console.clear?.();
console.log("Node REPL-Runner – Strg+C zum Beenden.");
promptWithDefault();

