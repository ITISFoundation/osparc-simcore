# UploadMgr

The UploadMgr contrib uploads files to the server, providing background uploads and progress feedback on modern browsers, falling back to traditional file upload on older browsers.  

## Benefits

  * Progress feedback during upload (where supported)
  * Queue multiple files for upload (on all browsers)
  * Uploads can be cancelled
  * Use the included UploadButton widget or write your own (trivial requirements)
  * Modular transport
  * No other UI widgets required, eg no form etc just a button

## Online Demo
You can view the online demo at http://www.zenesis.com/UploadMgr/uploadmgr/demo/default/build/index.html

# Getting Started
You need a UploadButton for the user to click and an UploadMgr to make the upload work:

``` 
var btn = new com.zenesis.qx.upload.UploadButton("Add File(s)", "myapp/test.png");
var uploader = new com.zenesis.qx.upload.UploadMgr(btn, "/demoupload");

var doc = this.getRoot();
doc.add(btn, { left: 50, top: 50 });
```

The constructor to UploadMgr takes two parameters – the first is the upload button that will open the browser’s “Open File” dialog, the second is the URL to upload to (ie the path that would normally be in a form element’s action attribute).

## Getting Progress Feedback

Every file that is to be uploaded is wrapped in an instance of com.zenesis.qx.upload.File, a normal Qooxdoo object that fires events during the upload process; it has these properties:

  * Size – the size of the file (if known)
  * Progress – the number of bytes uploaded so far
  * State – one of “not-started”, “uploading”, “cancelled”, “uploaded”
  * Response - the text returned from the server

The UploadMgr fires the “addFile” event when a new file has been added to the upload queue and passes an instance of com.zenesis.qx.upload.File as the event’s data property.

Attach listeners to com.zenesis.qx.upload.File to track progress:

``` javascript
uploader.addListener("addFile", function(evt) {
	var file = evt.getData();
	var progressListenerId = file.addListener("changeProgress", function(evt) {
		var file = evt.getTarget();
		var uploadedSize = evt.getData();
		
		this.debug("Upload " + file.getFilename() + ": " + 
			uploadedSize + " / " + file.getSize() + " - " +
   			Math.round(uploadedSize / file.getSize() * 100) + "%");
	}, this);
	// …snip… //
```

The "progress" property will give feedback about the quantity of data uploaded so far but is only available on browsers that support it (FF3+, Chrome, Safari, etc) so "changeProgress" may not fire; to cater for older browsers too, watch the “state” property:

``` javascript
// All browsers can at least get changes in state
var stateListenerId = file.addListener("changeState", function(evt) {
	var state = evt.getData();
	var file = evt.getTarget();
				
	if (state == "uploading")
		this.debug(file.getFilename() + " (Uploading...)");
	else if (state == "uploaded")
		this.debug(file.getFilename() + " (Complete)");
	else if (state == "cancelled")
		this.debug(file.getFilename() + " (Cancelled)");

	// Remove the listeners
	if (state == "uploaded" || state == "cancelled") {
		file.removeListenerById(progressListenerId);
		file.removeListenerById(stateListenerId);
	}
}, this);
```

Changes to the “state” property are a good opportunity to remove the listeners on the file, too.
Finally, the "response" property contains whatever was returned from the server.
## A more detailed example

Please see the Application.js for more detailed example.

### Multiple Upload Buttons

You can have more than one upload button attached to an UploadMgr instance - this allows you to have one queue of files uploading and put "upload" buttons where it makes most sense for usability.

``` javascript
var secondBtn = new com.zenesis.qx.upload.UploadButton("Add File(s)", 
    "myapp/test.png");

uploader.addWidget(secondBtn);
```

You can remove them later if you wish:
``` javascript
  // About to dispose of secondBtn - make uploader forget about it
  uploader.removeWidget(secondBtn);
  
  // ok to dispose
  secondBtn.dispose();
```

### Sending Parameters to the server
To add parameters to the upload you can use UploadMgr.setParam(name, value) to specify a name/value pair that will be sent with every upload.  
``` javascript
	uploader.setParam("MY_GLOBAL_PARAM", "some global value");
```

You can also set parameters on the widget that triggered the upload, and those parameters will only be sent for files uploaded via that widget.  This is useful where you have multiple upload widgets in different places in your application and you want to associate different parameters for each.

``` javascript
  btn.setParam("MY_WIDGET_PARAM", "which-widget-the-user-clicked");
```

Parameters set on the widget override global values set against the UploadMgr.
You can override parameters on a per-file basis in the UploadMgr's addFile event handler, for example:
``` javascript
uploader.addListener("addFile", function(evt) {
	var file = evt.getData();
	file.setParam("MY_GLOBAL_PARAM", "a different value");
	file.setParam("MY_FILE_PARAM", "some-value");
}
```

Note that in the example above, the file is given it's own value for MY_GLOBAL_PARAM - this overrides the previous global value, but only for this one file.  File parameters take precedence over widget values, and file and widget values take precedence over global values.  When overriding a global parameter value in this way, if you specify null as the value then the paramater will not be sent at all.

``` javascript
uploader.addListener("addFile", function(evt) {
	var file = evt.getData();

	// Do not send MY_GLOBAL_PARAM
	file.setParam("MY_GLOBAL_PARAM", null);
}
```

## Server Implementation

The UploadMgr on the client sends files as “multipart/formdata”, ie the same as a <form> tag in a non-Ajax application (note that previous versions used “application/octet-stream” but this is no longer required).  Your preferred server platform will already have implementations and examples available for you to use (just Google it).

Included in the contrib are examples for Java, PHP, and Perl.

**Note::** The Java example requires the O’Reilly com.oreilly.servlet library to handle “multipart/formdata” requests – this is available separately from http://www.servlets.com/cos/

## Changes / Status

7th Sep 2011 - the UploadMgr now supports multiple upload widgets, so the "widget" property has been removed and replaced with the addWidget() and removeWidget() APIs.

18th Oct 2011 - multipart/form-data encoding is now used for all uploads; if the browser implements the FormData API (FF4+, Chrome7+) then it is used to do the encoding, otherwise the encoding is done "by hand" in javascript.  This means that no special server coding is required.

28th Nov 2011 - parameters are now added to the File and UploadMgr objects, UploadHandler's addParam method is deprecated.

## Credits
The Qooxdoo contrib UploadWidget (http://qooxdoo.org/contrib/project/uploadwidget) has been around for ages and provides a stable and mature widget; the authors (Dietrich Streifert & Tobias Oetiker) did the heavy lifting of making an upload widget work in Qooxdoo.

Andrew Valums’ Ajax Upload project (http://valums.com/ajax-upload/) demonstrated using XmlHttpRequest for background uploads with feedback for modern browsers, and inspired this rewrite.

François de Metz wrote a Formdata shim (https://github.com/francois2metz/html5-formdata), Mozilla did a similar demno (http://demos.hacks.mozilla.org/openweb/imageUploader/js/extends/xhr.js) that were the inspiration for cross-browser multipart/form-data
