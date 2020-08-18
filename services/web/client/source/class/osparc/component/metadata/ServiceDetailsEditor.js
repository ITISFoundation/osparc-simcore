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

qx.Class.define("osparc.component.metadata.ServiceDetailsEditor", {
  extend: qx.ui.core.Widget,

  /**
    * @param serviceData {Object} Object containing the Service Data
    * @param winWidth {Number} Width for the window, needed for stretching the thumbnail
    */
  construct: function(serviceData, winWidth) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.Grow());

    this.__serviceData = serviceData;

    this.__stack = new qx.ui.container.Stack();
    this.__displayView = this.__createDisplayView(serviceData, winWidth);
    this.__editView = this.__createEditView();
    this.__stack.add(this.__displayView);
    this.__stack.add(this.__editView);
    this._add(this.__stack);
  },

  events: {
    "updateService": "qx.event.type.Event",
    "startService": "qx.event.type.Data"
  },

  properties: {
    mode: {
      check: ["display", "edit"],
      init: "display",
      nullable: false,
      apply: "_applyMode"
    }
  },

  members: {
    __stack: null,
    __fields: null,
    __openButton: null,
    __serviceData: null,
    __serviceVersionDetails: null,

    showOpenButton: function(show) {
      this.__openButton.setVisibility(show ? "visible" : "excluded");
    },

    __createDisplayView: function(serviceData, winWidth) {
      const displayView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      const serviceVersionDetails = this.__serviceVersionDetails = new osparc.component.metadata.ServiceVersionDetails(serviceData, winWidth);
      displayView.add(serviceVersionDetails, {
        flex: 1
      });
      let buttons = this.__createButtons();
      displayView.add(buttons);
      serviceVersionDetails.addListener("changeService", () => {
        displayView.remove(buttons);
        buttons = this.__createButtons();
        displayView.add(buttons);
      }, this);
      return displayView;
    },

    __createButtons: function() {
      const isCurrentUserOwner = this.__isUserOwner();

      const buttonsToolbar = new qx.ui.toolbar.ToolBar();

      if (isCurrentUserOwner) {
        const modeButton = new qx.ui.toolbar.Button(this.tr("Edit")).set({
          appearance: "toolbar-md-button"
        });
        osparc.utils.Utils.setIdToWidget(modeButton, "editServiceBtn");
        modeButton.addListener("execute", () => this.setMode("edit"), this);
        buttonsToolbar.add(modeButton);
      }

      buttonsToolbar.addSpacer();

      const openButton = this.__openButton = new qx.ui.toolbar.Button(this.tr("Open")).set({
        appearance: "toolbar-md-button"
      });
      osparc.utils.Utils.setIdToWidget(openButton, "startServiceBtn");
      openButton.addListener("execute", () => {
        const data = {
          "serviceKey": this.__serviceVersionDetails.getService().key,
          "serviceVersion": this.__serviceVersionDetails.getSelectedVersion()
        };
        this.fireDataEvent("startService", data);
      });
      buttonsToolbar.add(openButton);

      return buttonsToolbar;
    },

    __createEditView: function(isTemplate) {
      const isCurrentUserOwner = this.__isUserOwner();
      const fieldIsEnabled = isCurrentUserOwner;

      const editView = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));
      const buttonsToolbar = new qx.ui.toolbar.ToolBar();

      this.__fields = {
        name: new qx.ui.form.TextField(this.__serviceData.name).set({
          font: "title-18",
          height: 35,
          enabled: fieldIsEnabled
        }),
        description: new qx.ui.form.TextArea(this.__serviceData.description).set({
          enabled: fieldIsEnabled
        }),
        thumbnail: new qx.ui.form.TextField(this.__serviceData.thumbnail).set({
          enabled: fieldIsEnabled
        })
      };

      const {
        name,
        description,
        thumbnail
      } = this.__fields;
      editView.add(new qx.ui.basic.Label(this.tr("Title")).set({
        font: "text-14",
        marginTop: 20
      }));
      osparc.utils.Utils.setIdToWidget(name, "serviceDetailsEditorTitleFld");
      editView.add(name);
      editView.add(new qx.ui.basic.Label(this.tr("Description")).set({
        font: "text-14"
      }));
      osparc.utils.Utils.setIdToWidget(description, "serviceDetailsEditorDescFld");
      editView.add(description, {
        flex: 1
      });
      editView.add(new qx.ui.basic.Label(this.tr("Thumbnail")).set({
        font: "text-14"
      }));
      osparc.utils.Utils.setIdToWidget(thumbnail, "serviceDetailsEditorThumbFld");
      editView.add(thumbnail);

      const saveButton = new qx.ui.toolbar.Button(this.tr("Save"), "@FontAwesome5Solid/save/16").set({
        appearance: "toolbar-md-button"
      });
      osparc.utils.Utils.setIdToWidget(saveButton, "serviceDetailsEditorSaveBtn");
      saveButton.addListener("execute", e => {
        const btn = e.getTarget();
        btn.setIcon("@FontAwesome5Solid/circle-notch/16");
        btn.getChildControl("icon").getContentElement()
          .addClass("rotate");
        this.__saveService(btn);
      }, this);
      const cancelButton = new qx.ui.toolbar.Button(this.tr("Cancel")).set({
        appearance: "toolbar-md-button",
        enabled: isCurrentUserOwner
      });
      osparc.utils.Utils.setIdToWidget(cancelButton, "serviceDetailsEditorCancelBtn");
      cancelButton.addListener("execute", () => this.setMode("display"), this);

      buttonsToolbar.addSpacer();
      buttonsToolbar.add(saveButton);
      buttonsToolbar.add(cancelButton);
      editView.add(buttonsToolbar);

      return editView;
    },

    __saveService: function(btn) {
      const data = this.__serializeForm();
      const params = {
        url: osparc.data.Resources.getServiceUrl(
          this.__serviceVersionDetails.getService()["key"],
          this.__serviceVersionDetails.getSelectedVersion()
        ),
        data: data
      };
      osparc.data.Resources.fetch("services", "patch", params)
        .then(serviceData => {
          btn.resetIcon();
          btn.getChildControl("icon").getContentElement()
            .removeClass("rotate");
          this.__studyModel.set(serviceData);
          this.setMode("display");
          this.fireEvent("updateService");
        })
        .catch(err => {
          btn.resetIcon();
          btn.getChildControl("icon").getContentElement()
            .removeClass("rotate");
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the information."), "ERROR");
        });
    },

    __serializeForm: function() {
      const data = {};
      for (let key in this.__fields) {
        data[key] = this.__fields[key].getValue();
      }
      [
        "name",
        "description",
        "thumbnail"
      ].forEach(fieldKey => {
        const dirty = data[fieldKey];
        const clean = osparc.wrapper.DOMPurify.getInstance().sanitize(dirty);
        if (dirty && dirty !== clean) {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an issue in the text of ") + fieldKey, "ERROR");
        }
        data[fieldKey] = clean;
      }, this);
      return data;
    },

    _applyMode: function(mode) {
      switch (mode) {
        case "display":
          this.__stack.setSelection([this.__displayView]);
          break;
        case "edit":
          this.__stack.setSelection([this.__editView]);
          break;
      }
    },

    __isUserOwner: function() {
      const service = this.__serviceVersionDetails.getService();
      if (service) {
        return service.owner === osparc.auth.Data.getInstance().getEmail();
      }
      return false;
    }
  }
});
