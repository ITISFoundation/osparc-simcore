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
    
    var yamlSchema = yaml.safeDump(convertedSchema)
    // console.log(yamlSchema);
    
    // there is a BUG here. examples in a schema are not allowed in openapi, they should be replaced by example
    // Note that schemas and properties support singular example but not plural examples.
    // [link to problem](https://swagger.io/docs/specification/adding-examples/)
    yamlSchema = yamlSchema.replace(/examples:\n/g, "example:\n");
    // write as yaml
    fs.writeFileSync(outputPath + path.basename(filepath, ".json") + "-converted.yaml", yamlSchema);
    // fs.writeFileSync(outputPath + "converted_" + filepath, JSON.stringify(convertedSchema));    
  }
  
});
