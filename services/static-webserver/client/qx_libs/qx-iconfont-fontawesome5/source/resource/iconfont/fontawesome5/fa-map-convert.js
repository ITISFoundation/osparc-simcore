#!/usr/bin/env node
const yaml = require('js-yaml');
const fs = require('fs');

let res = {};
let doc = yaml.safeLoad(fs.readFileSync('icons.yml', 'utf8'));
for (let key in doc) {
   doc[key].styles.forEach((style) => {
      if (res[style] == undefined){
         res[style]= {};
      }
      res[style][key] = doc[key].unicode;
   });
}
for (let key in res) {
    fs.writeFileSync('fa-' + key + '.map', JSON.stringify(res[key]));
}
