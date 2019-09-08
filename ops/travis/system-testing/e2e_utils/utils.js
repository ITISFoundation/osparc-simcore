async function getPageTitle(page) {
  return await page.title();
}

function getPageUrl(page) {
  return page.url();
}

async function dragAndDrop(page, start, end) {
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  
  await page.mouse.move(end.x, end.y);
  await page.mouse.up();
}

require('dotenv').config();
const cloudinary = require('cloudinary');
cloudinary.config({
  cloud_name: process.env.CLOUD_NAME,
  api_key: process.env.CLOUD_API_KEY,
  api_secret: process.env.CLOUD_API_SECRET,
});

function cloudinaryPromise(shotResult, cloudinary_options){
  return new Promise(function(res, rej){
    cloudinary.v2.uploader.upload_stream(cloudinary_options,
      function (error, cloudinary_result) {
        if (error){
          console.error('Upload to cloudinary failed: ', error);
          rej(error);
        }
        res(cloudinary_result);
      }
    ).end(shotResult);
  });
}

async function doScreenCapture(page, captureName) {
  // details are skipped here. Refer to in previous step
  const shotResult = await page.screenshot({
    fullPage: true
  }).then((result) => {
    console.log(`${captureName} succeed.`);
    return result;
  }).catch(e => {
    console.error(`${captureName} failed`, e);
    return false;
  });

  const d = new Date();
  const current_time = `${d.getFullYear()}_${d.getMonth()+1}_${d.getDate()}_${d.getHours()}_${d.getMinutes()}`;
  const cloudinary_options = {
    public_id: `newCapture/${current_time}_${captureName}`
  };
  if (shotResult) {
    return cloudinaryPromise(shotResult, cloudinary_options);
  }
  else {
    return null;
  }
}

module.exports = {
  getPageTitle,
  getPageUrl,
  dragAndDrop,
  doScreenCapture,
}
