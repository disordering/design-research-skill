#!/usr/bin/env node

import fs from 'fs';
import path from 'path';
import { spawnSync } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');

const validBumps = new Set([
  'patch',
  'minor',
  'major',
  'prepatch',
  'preminor',
  'premajor',
  'prerelease',
]);

const validAccess = new Set(['public', 'restricted']);

function step(message) {
  console.log(`\n==> ${message}`);
}

function fail(message, details) {
  console.error(message);
  if (details) {
    console.error(details);
  }
  process.exit(1);
}

function parseArgs(argv) {
  const options = {
    bump: 'patch',
    version: '',
    access: '',
    checkOnly: false,
    noGitPush: false,
    noNpmPublish: false,
    skipPack: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];

    if (arg === '--check' || arg === '--check-only') {
      options.checkOnly = true;
      continue;
    }
    if (arg === '--no-git-push') {
      options.noGitPush = true;
      continue;
    }
    if (arg === '--no-npm-publish') {
      options.noNpmPublish = true;
      continue;
    }
    if (arg === '--skip-pack') {
      options.skipPack = true;
      continue;
    }
    if (arg === '--bump') {
      const value = argv[i + 1];
      if (!value || !validBumps.has(value)) {
        fail(`Invalid --bump value. Use one of: ${Array.from(validBumps).join(', ')}`);
      }
      options.bump = value;
      i += 1;
      continue;
    }
    if (arg === '--version') {
      const value = argv[i + 1];
      if (!value) {
        fail('Missing value for --version');
      }
      options.version = value;
      i += 1;
      continue;
    }
    if (arg === '--access') {
      const value = argv[i + 1];
      if (!value || !validAccess.has(value)) {
        fail('Invalid --access value. Use `public` or `restricted`.');
      }
      options.access = value;
      i += 1;
      continue;
    }

    fail(`Unknown argument: ${arg}`);
  }

  if (options.version && argv.includes('--bump')) {
    fail('Use either --bump or --version, not both.');
  }

  return options;
}

function run(command, args, { capture = false, allowFailure = false } = {}) {
  const label = [command, ...args].join(' ');
  console.log(`-> ${label}`);

  const result = spawnSync(command, args, {
    cwd: repoRoot,
    encoding: 'utf8',
    stdio: capture ? ['inherit', 'pipe', 'pipe'] : 'inherit',
    shell: process.platform === 'win32',
  });

  if (result.error) {
    fail(`Failed to run: ${label}`, result.error.message);
  }

  const stdout = capture ? (result.stdout || '').trim() : '';
  const stderr = capture ? (result.stderr || '').trim() : '';

  if (result.status !== 0 && !allowFailure) {
    fail(`Command failed: ${label}`, stderr || stdout);
  }

  return {
    status: result.status ?? 1,
    stdout,
    stderr,
  };
}

function readPackageJson() {
  const raw = fs.readFileSync(path.join(repoRoot, 'package.json'), 'utf8');
  return JSON.parse(raw);
}

const options = parseArgs(process.argv.slice(2));

process.chdir(repoRoot);

step('Checking required tools');
run('git', ['--version']);
run('npm', ['--version']);

step('Checking git working tree');
const gitStatus = run('git', ['status', '--porcelain'], { capture: true });
if (gitStatus.stdout) {
  fail('Working tree is not clean. Commit or stash changes before releasing.');
}

step('Checking npm login');
const whoami = run('npm', ['whoami'], { capture: true, allowFailure: true });
if (whoami.status !== 0 || !whoami.stdout) {
  fail('npm login is required before publishing. Run `npm login` first, then rerun this script.', whoami.stderr);
}
console.log(`Logged in as: ${whoami.stdout}`);

step('Checking published version');
const pkg = readPackageJson();
const published = run('npm', ['view', pkg.name, 'version'], { capture: true, allowFailure: true });
if (published.status === 0 && published.stdout) {
  console.log(`Latest npm version: ${published.stdout}`);
} else {
  console.log('Package not found on npm yet, or version lookup failed.');
}
console.log(`Local version: ${pkg.version}`);

if (options.checkOnly) {
  step('Preflight complete');
  console.log('Checks passed. No version bump or publish was performed.');
  process.exit(0);
}

step('Bumping version');
if (options.version) {
  run('npm', ['version', options.version]);
} else {
  run('npm', ['version', options.bump]);
}

const nextPkg = readPackageJson();
console.log(`New version: ${nextPkg.version}`);

if (!options.skipPack) {
  step('Previewing publish payload');
  run('npm', ['pack', '--dry-run']);
}

if (!options.noNpmPublish) {
  step('Publishing to npm');
  const publishArgs = ['publish'];
  if (options.access) {
    publishArgs.push('--access', options.access);
  }
  run('npm', publishArgs);
}

if (!options.noGitPush) {
  step('Pushing git commit and tag');
  run('git', ['push']);
  run('git', ['push', '--tags']);
}

step('Release complete');
console.log(`Published ${nextPkg.name}@${nextPkg.version}`);
