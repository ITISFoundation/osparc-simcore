/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * A file input that allows the user to select a file and stores its content.
 */
qx.Class.define("osparc.ui.form.FileInput", {
  extend: qx.ui.core.Widget,
  construct: function(extensions, multiple) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(5).set({
      alignY: "middle"
    }));
    this.set({
      marginTop: 3
    });

    if (extensions) {
      this.setExtensions(extensions);
    }
    if (multiple) {
      this.setMultiple(multiple);
    }
    this.__input = new qx.html.Input("file", {
      display: "none"
    }, {
      accept: this.getExtensions().map(ext => "." + ext).join(","),
      multiple
    });
    this.getContentElement().add(this.__input);

    this.__selectBtn = new qx.ui.form.Button(this.tr("Select File..."));
    this._add(this.__selectBtn);

    this.__selectedFiles = new qx.ui.basic.Label();
    this._add(this.__selectedFiles);

    this.__attachEventHandlers();
  },

  properties: {
    extensions: {
      check: "Array",
      init: []
    },
    multiple: {
      check: "Boolean",
      init: false
    }
  },

  events: {
    "selectionChanged": "qx.event.type.Event"
  },

  members: {
    __input: null,
    __selectBtn: null,
    __selectedFiles: null,

    getButton: function() {
      return this.__selectBtn;
    },

    __attachEventHandlers: function() {
      this.__input.addListener("change", () => {
        const fileNames = [];
        const files = this.__input.getDomElement().files;
        for (let i=0; i<files.length; i++) {
          fileNames.push(files[i].name);
        }
        this.__selectedFiles.setValue(fileNames.join("; "));
        this.fireEvent("selectionChanged");
      }, this);
      this.__selectBtn.addListener("execute", () => {
        this.__input.getDomElement().click();
      }, this);
    },

    getSelectedFilesLabel: function() {
      return this.__selectedFiles;
    },

    getValue: function() {
      const file = this.__input.getDomElement().files.item(0);
      return file ? file.name : null;
    },

    getFile: function() {
      return this.__input.getDomElement().files.item(0);
    }
  }
});
