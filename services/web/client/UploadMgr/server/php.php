<?php

/* ***********************************************************************

   QxUploadMgr - provides an API for uploading one or multiple files
   with progress feedback (on modern browsers), does not block the user 
   interface during uploads, supports cancelling uploads.

   http://qooxdoo.org

   Copyright:
     2011 Zenesis Limited, http://www.zenesis.com

   License:
     LGPL: http://www.gnu.org/licenses/lgpl.html
     EPL: http://www.eclipse.org/org/documents/epl-v10.php
     
     This software is provided under the same licensing terms as Qooxdoo,
     please see the LICENSE file in the Qooxdoo project's top-level directory 
     for details.

     Parts of this code is based on the work by Andrew Valums (andrew@valums.com)
     and is covered by the GNU GPL and GNU LGPL2 licenses; please see
     http://valums.com/ajax-upload/.

   Authors:
     * John Spackman (john.spackman@zenesis.com)

************************************************************************/

class QxUploadMgr {

	/**
	 * Handles the upload
	 * @param $uploadDirectory {String} the path to upload to
	 * @param $replaceOldFile {Boolean} whether to replace existing files
	 */
	public static function handleUpload($uploadDirectory, $replaceOldFile = FALSE) {
        if (!is_writable($uploadDirectory))
            throw new Exception("Server error. Upload directory isn't writable.");
            
        /*if ($_SERVER['CONTENT_TYPE'] == "application/octet-stream")
            return QxUploadMgr::handleApplicationOctet($uploadDirectory, $replaceOldFile);
        else*/
            return QxUploadMgr::handleMultipartFormData($uploadDirectory, $replaceOldFile);
	}
	
	/**
	 * Determins the filename for the upload
	 * @param $uploadDirectory {String} the path to upload to
	 * @param $originalName {String} the filename as given by the browser
	 * @param $replaceOldFile {Boolean} whether to replace existing files
	 */
	public static function getFilename($uploadDirectory, $originalName, $replaceOldFile) {
        $pathinfo = pathinfo($originalName);
        $filename = $uploadDirectory . '/' . $pathinfo['filename'] . '.' . $pathinfo['extension'];

        if (!$replaceOldFile){
        	$index = 1;
            while (file_exists($filename)) {
		        $filename = $uploadDirectory . '/' . $pathinfo['filename'] . '-' . $index . '.' . $pathinfo['extension'];
		        $index++;
            }
        }
        return $filename;
	}
	
	/**
	 * Handles the upload where content type is "application/octet-stream"
	 * @param $uploadDirectory {String} the path to upload to
	 * @param $replaceOldFile {Boolean} whether to replace existing files
	 */
	public static function handleApplicationOctet($uploadDirectory, $replaceOldFile) {
		$filename = QxUploadMgr::getFilename($uploadDirectory, $_SERVER['HTTP_X_FILE_NAME'], $replaceOldFile);
        error_log("Receiving application/octet-stream into $filename");
        
        $input = fopen("php://input", "r");
        $target = fopen($filename, "w");        
        $realSize = stream_copy_to_stream($input, $target);
        fclose($input);
        fclose($target);
        
        if (isset($_SERVER["CONTENT_LENGTH"])) {
            $expectedSize = (int)$_SERVER["CONTENT_LENGTH"];
            if ($realSize != $expectedSize)
            	return array('error' => 'File is the wrong size');
        }
        
        return array('success'=>true);
    }
	
	/**
	 * Handles the upload where content type is "multipart/form-data"
	 * @param $uploadDirectory {String} the path to upload to
	 * @param $replaceOldFile {Boolean} whether to replace existing files
	 */
    public static function handleMultipartFormdata($uploadDirectory, $replaceOldFile) {
    error_log("hello, count()=" . $_FILES.count());
    	foreach ($_FILES as $file) {
    		error_log("$file=" . $file);
    		$filename = QxUploadMgr::getFilename($uploadDirectory, $file['name'], $replaceOldFile);
	        error_log("Receiving multipart/formdata into $filename");
    		if (!move_uploaded_file($file['tmp_name'], $filename)) {
    			error_log("Failed to move uploaded file from ". $file['tmp_name']. " to $filename");
    			return array('error' => 'Failed to move uploaded file');
    		}
    	}
        
        return array('success'=>true);
    }
}

$result = QxUploadMgr::handleUpload('uploads');

// to pass data through iframe you will need to encode all html tags
echo htmlspecialchars(json_encode($result), ENT_NOQUOTES);
