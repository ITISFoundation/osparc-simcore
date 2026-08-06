#!/usr/bin/env node
// Converts Font Awesome's metadata/icons.yml into the per-style name->unicode
// mapping files (fa-<style>.json) that qooxdoo consumes (see Manifest.json).
//
// Only the styles shipped in Font Awesome Free are emitted. Icon aliases
// (e.g. the legacy v5 name "cog" for the v6 "gear") are included as well so
// that references using legacy names keep resolving after the upgrade.
const yaml = require('js-yaml');
const fs = require('fs');

const FREE_STYLES = ['solid', 'regular', 'brands'];
const iconsYml = process.argv[2] || 'icons.yml';

let res = {};
let doc = yaml.safeLoad(fs.readFileSync(iconsYml, 'utf8'));
for (let key in doc) {
   let icon = doc[key];
   if (!icon || !icon.unicode || !Array.isArray(icon.styles)) {
      continue;
   }
   let names = [key];
   if (icon.aliases && Array.isArray(icon.aliases.names)) {
      names = names.concat(icon.aliases.names);
   }
   icon.styles.forEach((style) => {
      if (FREE_STYLES.indexOf(style) === -1) {
         return;
      }
      if (res[style] == undefined) {
         res[style] = {};
      }
      names.forEach((name) => {
         res[style][name] = icon.unicode;
      });
   });
}
FREE_STYLES.forEach((style) => {
   let sorted = {};
   Object.keys(res[style] || {}).sort().forEach((name) => {
      sorted[name] = res[style][name];
   });
   fs.writeFileSync('fa-' + style + '.json', JSON.stringify(sorted));
});
