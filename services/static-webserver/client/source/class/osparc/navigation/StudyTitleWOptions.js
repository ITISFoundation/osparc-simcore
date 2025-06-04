/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.navigation.StudyTitleWOptions", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10).set({
      alignY: "middle",
      alignX: "center"
    }));

    this.getChildControl("study-menu-button");
    this.getChildControl("edit-title-label");
  },

  events: {
    "openLogger": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: true,
      event: "changeStudy",
      apply: "__applyStudy"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "study-menu-info":
          control = new qx.ui.menu.Button().set({
            label: this.tr("Information..."),
            icon: "@MaterialIcons/info_outline/14",
            ...this.self().BUTTON_OPTIONS
          });
          control.addListener("execute", () => {
            let widget = null;
            if (this.getStudy().isPipelineMononode()) {
              widget = new osparc.info.MergedLarge(this.getStudy());
            } else {
              widget = new osparc.info.StudyLarge(this.getStudy());
            }
            const title = this.tr("Information");
            const width = osparc.info.CardLarge.WIDTH;
            const height = osparc.info.CardLarge.HEIGHT;
            osparc.ui.window.Window.popUpInWindow(widget, title, width, height).set({
              maxHeight: height
            });
          });
          break;
        case "study-menu-reload":
          control = new qx.ui.menu.Button().set({
            label: this.tr("Reload"),
            icon: "@FontAwesome5Solid/redo-alt/12",
          });
          control.addListener("execute", () => this.__reloadIFrame(), this);
          break;
        case "study-menu-conversations":
          control = new qx.ui.menu.Button().set({
            label: this.tr("Conversations"),
            icon: "@FontAwesome5Solid/comments/12",
          });
          control.addListener("execute", () => osparc.study.Conversations.popUpInWindow(this.getStudy().serialize()), this);
          break;
        case "study-menu-convert-to-pipeline":
          control = new qx.ui.menu.Button().set({
            label: this.tr("Convert to Pipeline"),
            icon: null,
          });
          control.addListener("execute", () => this.__convertToPipelineClicked(), this);
          break;
        case "study-menu-restore":
          control = new qx.ui.menu.Button().set({
            label: this.tr("Restore"),
            icon: osparc.theme.common.Image.URLS["window-restore"] + "/20",
          });
          control.addListener("execute", () => {
            this.getStudy().getUi().setMode("workbench");
          });
          break;
        case "study-menu-open-logger":
          control = new qx.ui.menu.Button().set({
            label: this.tr("Platform Logs..."),
            icon: "@FontAwesome5Solid/download/14"
          });
          control.addListener("execute", () => this.fireEvent("openLogger"));
          break;
        case "study-menu-button": {
          const optionsMenu = new qx.ui.menu.Menu();
          optionsMenu.setAppearance("menu-wider");
          optionsMenu.add(this.getChildControl("study-menu-info"));
          optionsMenu.add(this.getChildControl("study-menu-reload"));
          optionsMenu.add(this.getChildControl("study-menu-conversations"));
          if (osparc.product.Utils.showConvertToPipeline()) {
            optionsMenu.add(this.getChildControl("study-menu-convert-to-pipeline"));
          }
          optionsMenu.add(this.getChildControl("study-menu-open-logger"));
          control = new qx.ui.form.MenuButton().set({
            appearance: "fab-button",
            menu: optionsMenu,
            icon: "@FontAwesome5Solid/ellipsis-v/14",
            allowGrowY: false,
            width: 24,
          });
          this._add(control);
          break;
        }
        case "edit-title-label":
          control = new osparc.ui.form.EditLabel().set({
            labelFont: "text-14",
            inputFont: "text-14",
            maxWidth: 300
          });
          control.addListener("editValue", e => {
            const newLabel = e.getData();
            this.getStudy().setName(newLabel);
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __reloadIFrame: function() {
      const nodes = this.getStudy().getWorkbench().getNodes();
      if (Object.keys(nodes).length === 1) {
        Object.values(nodes)[0].getIframeHandler().restartIFrame();
      }
    },

    __applyStudy: function(study) {
      if (study) {
        const editTitle = this.getChildControl("edit-title-label");
        study.bind("name", editTitle, "value");

        const reloadButton = this.getChildControl("study-menu-reload");
        study.getUi().bind("mode", reloadButton, "visibility", {
          converter: mode => mode === "standalone" ? "visible" : "excluded"
        });

        const conversationsButton = this.getChildControl("study-menu-conversations");
        study.getUi().bind("mode", conversationsButton, "visibility", {
          converter: mode => mode === "standalone" ? "visible" : "excluded"
        });

        if (osparc.product.Utils.showConvertToPipeline()) {
          const convertToPipelineButton = this.getChildControl("study-menu-convert-to-pipeline");
          study.getUi().bind("mode", convertToPipelineButton, "visibility", {
            converter: mode => mode === "standalone" ? "visible" : "excluded"
          });
        }

        const loggerButton = this.getChildControl("study-menu-open-logger");
        study.getUi().bind("mode", loggerButton, "visibility", {
          converter: mode => mode === "standalone" ? "visible" : "excluded"
        });
      } else {
        this.exclude();
      }
    },

    __convertToPipelineClicked: function() {
      let message = this.tr("Would you like to convert this project to a pipeline?");
      message += "<br>" + this.tr("If you want to create a copy of the project and convert the copy instead, please close the project first.");
      const confirmationWin = new osparc.ui.window.Confirmation();
      confirmationWin.set({
        caption: this.tr("Convert to Pipeline"),
        confirmText: this.tr("Convert"),
        confirmAction: "create",
        message,
      });
      confirmationWin.addListener("close", () => {
        if (confirmationWin.getConfirmed()) {
          this.getStudy().getUi().setMode("pipeline");
          osparc.FlashMessenger.logAs(this.tr("Project converted to pipeline"), "INFO");
        }
      });
      confirmationWin.open();
    },
  }
});
