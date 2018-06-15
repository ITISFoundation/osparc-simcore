package com.zenesis.qx.upload;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.PrintWriter;

import javax.servlet.ServletConfig;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

import org.apache.logging.log4j.Logger;

import com.oreilly.servlet.multipart.FilePart;
import com.oreilly.servlet.multipart.MultipartParser;
import com.oreilly.servlet.multipart.ParamPart;
import com.oreilly.servlet.multipart.Part;

/**
 * Servlet to demo the new uploader, Qx version of http://valums.com/ajax-upload/
 * @author john
 *
 */
public class DemoUploadServlet extends HttpServlet {
	
	private static final Logger log = org.apache.logging.log4j.LogManager.getLogger(DemoUploadServlet.class); 

    private static final long serialVersionUID = 1L;
    private File uploadFilesToDir;

    /**
     * {@inheritDoc}
     * @param config
     * @throws ServletException
     */
    @Override
    public void init(ServletConfig config) throws ServletException {
        super.init(config);
        String strUploadFilesTo = config.getInitParameter("uploadFilesTo");
        if (strUploadFilesTo == null || strUploadFilesTo.trim().length() == 0)
            uploadFilesToDir = (File)config.getServletContext().getAttribute("javax.servlet.context.tempdir");
        else
        	uploadFilesToDir = new File(strUploadFilesTo);
        uploadFilesToDir.mkdirs();
    }

    /* (non-Javadoc)
	 * @see javax.servlet.http.HttpServlet#doOptions(javax.servlet.http.HttpServletRequest, javax.servlet.http.HttpServletResponse)
	 */
	@Override
	protected void doOptions(HttpServletRequest request, HttpServletResponse response) throws ServletException, IOException {
		super.doOptions(request, response);
		
		/*
		 * NOTE:: This is used to allow posts from ANY website to this server - this is so that the demo browser
		 * (http://demo.qooxdoo.org/contrib/demobrowser/) is able to have something to upload to, but it's likely
		 * that you won't want this in your code because it's a security risk.
		 */
		if (request.getHeader("Access-Control-Request-Method").equals("POST")) {
			String origin = request.getHeader("Origin");
			log.info("Received request for Origin: " + origin + " from " + request.getRemoteAddr());
			response.setHeader("Access-Control-Allow-Origin", "*");
			response.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
			response.setHeader("Access-Control-Allow-Headers", "content-type,x-file-name,x-requested-with");
			response.setHeader("Access-Control-Max-Age", "100");
			response.setHeader("Vary", "Accept-Encoding");
			response.setHeader("Accept-Encoding", "gzip");
			response.setHeader("Connection", "Keep-Alive");
			response.setHeader("Content-Type", "text/plain");
		}
	}

	/** 
     * Handles the HTTP <code>POST</code> method.
     * @param request servlet request
     * @param response servlet response
     * @throws ServletException if a servlet-specific error occurs
     * @throws IOException if an I/O error occurs
     */
    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response) throws ServletException {
    	PrintWriter writer = null;

    	// Requored only for cross-origin requests (@see doOptions())
		response.setHeader("Access-Control-Allow-Origin", "*");

        try {
            writer = response.getWriter();
        } catch (IOException ex) {
            log(DemoUploadServlet.class.getName() + "has thrown an exception: " + ex.getMessage());
        }

        String contentType = request.getContentType();
        int pos = contentType.indexOf(';');
        if (pos > -1)
        	contentType = contentType.substring(0, pos);
        try {
        	// Older browsers
        	if (contentType.equals("multipart/form-data"))
        		receiveMultipart(request);
        	
        	// Modern browsers
        	else if (contentType.equals("application/octet-stream"))
        		receiveOctetStream(request);
        	
        	// Err - don't know
        	else {
                response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
                writer.print("{ \"success\": false }");
                log.error(DemoUploadServlet.class.getName() + " received request to upload unknown content type: " + contentType);
                return;
        	}
        	
            response.setStatus(HttpServletResponse.SC_OK);
            writer.print("{ \"success\": true}");
            
        } catch (IOException ex) {
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            writer.print("{ \"success\": false}");
            log.error(DemoUploadServlet.class.getName() + " has thrown an exception: " + ex.getMessage(), ex);
        }

        writer.flush();
        writer.close();
    }
    
    private void receiveMultipart(HttpServletRequest request) throws IOException {
		MultipartParser parser = new MultipartParser(request, Integer.MAX_VALUE, true, true, null);
		Part part;
		while ((part = parser.readNextPart()) != null) {
			if (part.isFile()) {
				// Get the file details
				FilePart filePart = (FilePart) part;
				filePart.setRenamePolicy(null);
				String filename = filePart.getFileName();
				
				// Save the file
	            receiveFile(filePart.getInputStream(), new File(uploadFilesToDir, filename));
			} else {
				ParamPart paramPart = (ParamPart) part;
				log.info("received param " + paramPart.getName() + "=" + paramPart.getStringValue());
			}
		}
    }
    
    private void receiveOctetStream(HttpServletRequest request) throws IOException {
        String filename = request.getHeader("X-File-Name");
        int pos = filename.lastIndexOf('/');
        if (pos > -1)
        	filename = filename.substring(pos + 1);
       	receiveFile(request.getInputStream(), new File(uploadFilesToDir, filename));
    }
    
    private void receiveFile(InputStream is, File dest) throws IOException {
    	log.info("Saving file to " + dest.getAbsolutePath());
        FileOutputStream fos = null;
        try {
            fos = new FileOutputStream(dest);
            byte[] buffer = new byte[32 * 1024];
            int len;
            while ((len = is.read(buffer)) > -1)
            	fos.write(buffer, 0, len);
        } catch(IOException e) {
        	dest.delete();
        } finally {
        	if (fos != null)
        		try { fos.close(); } catch (IOException ignored) {};
        	if (is != null)
        		try { is.close(); } catch (IOException ignored) {};
        }
    }
    
}
