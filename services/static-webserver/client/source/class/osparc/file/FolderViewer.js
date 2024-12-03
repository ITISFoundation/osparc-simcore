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
 *
 */

qx.Class.define("osparc.file.FolderViewer", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.setPaddingLeft(10);

    const folderUpBtn = this.getChildControl("folder-up");
    folderUpBtn.addListener("execute", () => this.fireDataEvent("folderUp", this.getFolder()), this);
    this.getChildControl("folder-path");
    const iconsButton = this.getChildControl("view-options-icons");
    const listButton = this.getChildControl("view-options-list");
    const folderContent = this.getChildControl("folder-content");

    this.bind("folder", this.getChildControl("folder-up"), "enabled", {
      converter: folder => Boolean(folder && folder.getPathLabel && folder.getPathLabel().length > 1)
    });

    this.bind("folder", this.getChildControl("folder-path"), "value", {
      converter: folder => folder ? folder.getPathLabel().join(" / ") : this.tr("Select folder")
    });

    this.bind("folder", folderContent, "folder");

    iconsButton.addListener("execute", () => folderContent.setMode("icons"));
    listButton.addListener("execute", () => folderContent.setMode("list"));

    folderContent.addListener("selectionChanged", e => this.fireDataEvent("selectionChanged", e.getData()));
    folderContent.addListener("itemSelected", e => this.fireDataEvent("itemSelected", e.getData()));
    folderContent.addListener("requestDatasetFiles", e => this.fireDataEvent("requestDatasetFiles", e.getData()));
  },

  properties: {
    folder: {
      check: "qx.core.Object",
      init: null,
      nullable: true,
      event: "changeFolder",
    },
  },

  events: {
    "selectionChanged": "qx.event.type.Data", // tap
    "itemSelected": "qx.event.type.Data", // dbltap
    "folderUp": "qx.event.type.Data",
    "requestDatasetFiles": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "header":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          this._add(control);
          break;
        case "folder-up": {
          const header = this.getChildControl("header");
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/arrow-up/12").set({
            enabled: false
          });
          header.addAt(control, 0);
          break;
        }
        case "folder-path": {
          const header = this.getChildControl("header");
          control = new qx.ui.basic.Label(this.tr("Select folder")).set({
            font: "text-14",
            allowGrowX: true,
            alignY: "middle",
            marginLeft: 10,
            marginRight: 10
          });
          header.addAt(control, 1, {
            flex: 1
          });
          break;
        }
        case "view-options-rgroup":
          control = new qx.ui.form.RadioGroup();
          break;
        case "view-options-icons": {
          control = new qx.ui.form.ToggleButton(null, "@MaterialIcons/apps/18");
          const group = this.getChildControl("view-options-rgroup");
          group.add(control);
          const header = this.getChildControl("header");
          header.addAt(control, 2);
          break;
        }
        case "view-options-list": {
          control = new qx.ui.form.ToggleButton(null, "@MaterialIcons/reorder/18");
          const group = this.getChildControl("view-options-rgroup");
          group.add(control);
          const header = this.getChildControl("header");
          header.addAt(control, 3);
          break;
        }
        case "folder-content": {
          control = new osparc.file.FolderContent();
          this._add(control, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },
  }
});
