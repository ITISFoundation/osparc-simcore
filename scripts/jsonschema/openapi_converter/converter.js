const toOpenApi = require('json-schema-to-openapi-schema');

const fs = require('fs');
const path = require('path');

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
    fs.writeFileSync(outputPath + "converted_" + filepath, JSON.stringify(convertedSchema))    
  }
  
});
