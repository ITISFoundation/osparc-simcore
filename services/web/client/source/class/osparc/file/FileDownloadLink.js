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
    const downloadLinkField = this.__downloadLinkField = this._createChildControlImpl("downloadLink");

    const selectButton = this._createChildControlImpl("selectButton");
    selectButton.addListener("execute", () => {
      const downloadLink = downloadLinkField.getValue();
      this.fireDataEvent("fileLinkAdded", downloadLink);
    }, this);
  },

  events: {
    "fileLinkAdded": "qx.event.type.Data"
  },

  statics: {
    getOutputLabel: function(outputValue) {
      if ("outFile" in outputValue) {
        const outInfo = outputValue["outFile"];
        if ("label" in outInfo) {
          return outInfo.label;
        }
        if ("downloadLink" in outInfo) {
          return osparc.file.FileDownloadLink.extractLabelFromLink(outInfo.downloadLink);
        }
      }
      return "";
    },

    extractLabelFromLink: function(downloadLink) {
      // until question mark
      const regex = "(^.*)(?=\\?)";
      const found = downloadLink.match(regex);
      if (found && found.length > 1) {
        const parts = found[1].split("/");
        return parts[parts.length - 1];
      }
      return "";
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
    __downloadLinkField: null,

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
    },

    getValue: function() {
      return this.__downloadLinkField.getValue();
    },

    setValue: function(value) {
      this.__downloadLinkField.setValue(value);
    }
  }
});
