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

qx.Class.define("osparc.component.study.Import", {
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
    this._add(fileInput);

    const importBtn = new osparc.ui.form.FetchButton(this.tr("Import")).set({
      alignX: "right",
      allowGrowX: false
    });
    importBtn.addListener("execute", () => {
      if (fileInput.getFile()) {
        const formData = {
          files: []
        };
        formData.files.push(fileInput.getFile());
        this.__sendFile(formData, importBtn);
      }
    }, this);
    this._add(importBtn);
  },

  events: {
    "studyImported": "qx.event.type.Data"
  },

  members: {
    __sendFile: function(formData, btn) {
      const headers = new Headers();
      headers.append("Accept", "application/json");
      const body = new FormData();
      body.append("metadata", new Blob([JSON.stringify(formData.json)], {
        type: "application/json"
      }));
      if (formData.files && formData.files.length) {
        const size = formData.files[0].size;
        const maxSize = 10; // 10 GB
        if (size > maxSize * 1024 * 1024 * 1024) {
          osparc.component.message.FlashMessenger.logAs(`The file is too big. Maximum size is ${maxSize}MB. Please provide with a smaller file or a repository URL.`, "ERROR");
          return;
        }
        body.append("attachment", formData.files[0], formData.files[0].name);
      }
      btn.setFetching(true);
      fetch("/v0/prjects:import", {
        method: "POST",
        headers,
        body
      })
        .then(resp => {
          if (resp.ok) {
            osparc.component.message.FlashMessenger.logAs("Study successfuly uploaded. Processing data...", "INFO");
            this.fireEvent("studyImported");
          } else {
            osparc.component.message.FlashMessenger.logAs(`A problem occured: ${resp.statusText}`, "ERROR");
          }
        })
        .finally(() => btn.setFetching(false));
    }
  }
});
