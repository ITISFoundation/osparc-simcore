/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that provides a way to use a download link
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let typeDownloadLink = new osparc.file.FileDownloadLink();
 *   this.getRoot().add(typeDownloadLink);
 * </pre>
 */

qx.Class.define("osparc.file.FileDownloadLink", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(5));

    const downloadLinkField = this.getChildControl("downloadLinkField");

    const selectButton = this.getChildControl("selectButton");
    selectButton.addListener("execute", () => {
      const downloadLink = downloadLinkField.getValue();
      if (osparc.utils.Utils.isValidHttpUrl(downloadLink)) {
        this.fireDataEvent("fileLinkAdded", downloadLink);
      } else {
        downloadLinkField.resetValue();
        osparc.FlashMessenger.getInstance().logAs(this.tr("Error checking link"), "WARNING");
      }
    }, this);
  },

  events: {
    "fileLinkAdded": "qx.event.type.Data"
  },

  statics: {
    extractLabelFromLink: function(downloadLink) {
      // works for sparc.science portal download links
      // http://www.mydomain.com/my_file.ext?word=blah
      // until question mark
      const regex = "(^.*)(?=\\?)";
      const found = downloadLink.match(regex);
      if (found && found.length > 1) {
        const parts = found[1].split("/");
        return parts[parts.length - 1];
      }

      const idx = downloadLink.lastIndexOf("/");
      if (idx > -1) {
        return downloadLink.substring(idx + 1);
      }

      return "unknown";
    },

    checkFileExists: function(urlToFile) {
      return new Promise(resolve => {
        const xhr = new XMLHttpRequest();
        xhr.open("HEAD", urlToFile, true);
        xhr.onreadystatechange = function() {
          if (xhr.readyState === 4) { // 4=this.DONE
            resolve(true);
          } else {
            resolve(false);
          }
        };
        xhr.send();
      });
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "downloadLinkField":
          control = new qx.ui.form.TextField().set({
            placeholder: this.tr("Type a Link")
          });
          this._add(control, {
            flex: 1
          });
          break;
        case "checkButton":
          control = new qx.ui.form.Button(this.tr("Validate"));
          this._add(control);
          break;
        case "checkLink":
          control = new qx.ui.basic.Image();
          control.set({
            source: "@FontAwesome5Solid/question-circle/14"
          });
          this._add(control);
          break;
        case "selectButton":
          control = new qx.ui.form.Button(this.tr("Select"));
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    getValue: function() {
      return this.getChildControl("downloadLinkField").getValue();
    },

    setValue: function(value) {
      this.getChildControl("downloadLinkField").setValue(value);
    }
  }
});
