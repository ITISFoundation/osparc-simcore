const toOpenApi = require('json-schema-to-openapi-schema');

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml')

const inputPath = '/input';
const outputPath = '/output/';


const filenames =  fs.readdirSync(inputPath)    

filenames.forEach(filepath => {
  const extName = path.extname(filepath);
  if (extName == ".json") {
    console.log("converting " + filepath + "...");
    const contents = fs.readFileSync(inputPath + "/" + filepath, 'utf8');    
    const object = JSON.parse(contents);
    const convertedSchema = toOpenApi(object);
    console.log("converted " + filepath + " succesfully");
    // write as yaml
    fs.writeFileSync(outputPath + path.basename(filepath, ".json") + ".yaml", yaml.safeDump(convertedSchema));
    //fs.writeFileSync(outputPath + "converted_" + filepath, JSON.stringify(convertedSchema));    
  }
  
});
