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
 *   let filesAdd = new osparc.file.FileDownloadLink();
 *   this.getRoot().add(filesAdd);
 * </pre>
 */

qx.Class.define("osparc.file.FileDownloadLink", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(5));
    const downloadLinkField = this._createChildControlImpl("downloadLink");
    const checkButton = this._createChildControlImpl("checkButton");
    const checkLink = this._createChildControlImpl("checkLink");
    const selectButton = this._createChildControlImpl("selectButton");

    checkButton.addListener("execute", () => {
      const downloadLink = downloadLinkField.getValue();
      this.self().checkFileExists(downloadLink)
        .then(exists => {
          if (exists) {
            checkLink.setSource("@FontAwesome5Solid/check-circle/14");
          } else {
            checkLink.setSource("@FontAwesome5Solid/times-circle/14");
          }
        });
    }, this);

    selectButton.addListener("execute", () => {
      const downloadLink = downloadLinkField.getValue();
      this.fireDataEvent("fileLinkAdded", downloadLink);
    }, this);
  },

  events: {
    "fileLinkAdded": "qx.event.type.Data"
  },

  statics: {
    checkFileExists: function(urlToFile) {
      return new Promise(resolve => {
        const http = new XMLHttpRequest();
        http.open("HEAD", urlToFile, true);
        http.onreadystatechange = function() {
          if (this.readyState === this.DONE) {
            resolve(true);
          } else {
            resolve(false);
          }
        };
        http.send();
      });
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "downloadLink":
          control = new qx.ui.form.TextField().set({
            placeholder: this.tr("Type a Download Link")
          });
          this._add(control, {
            flex: 1
          });
          break;
        case "checkButton":
          control = new qx.ui.toolbar.Button(this.tr("Validate"));
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
          control = new qx.ui.toolbar.Button(this.tr("Select"));
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    }
  }
});
