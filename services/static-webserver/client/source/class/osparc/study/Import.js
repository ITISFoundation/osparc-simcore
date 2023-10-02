/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @ignore(Headers)
 */

qx.Class.define("osparc.study.Import", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    // WEBSERVER_MAX_UPLOAD_FILE_SIZE_GB
    const subtitle = new qx.ui.basic.Label(this.tr("Max file size 10GB")).set({
      font: "text-12"
    });
    this._add(subtitle);

    const extensions = ["osparc"];
    const multiple = false;
    const fileInput = new osparc.ui.form.FileInput(extensions, multiple);
    fileInput.getSelectedFilesLabel().setMaxWidth(250);
    this._add(fileInput);

    const importBtn = new qx.ui.form.Button(this.tr("Import")).set({
      alignX: "right",
      allowGrowX: false
    });
    importBtn.addListener("execute", () => {
      const file = fileInput.getFile();
      if (file) {
        const size = file.size;
        const maxSize = 10 * 1000 * 1000 * 1000; // 10 GB
        if (size > maxSize) {
          osparc.FlashMessenger.logAs(`The file is too big. Maximum size is ${maxSize}MB. Please provide with a smaller file or a repository URL.`, "ERROR");
          return;
        }
        this.fireDataEvent("fileReady", file);
      }
    }, this);
    this._add(importBtn);
  },

  events: {
    "fileReady": "qx.event.type.Data"
  }
});
