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
        case "study-menu-convert-to-pipeline":
          control = new qx.ui.menu.Button().set({
            label: this.tr("Convert to Pipeline"),
            icon: null,
          });
          control.addListener("execute", () => {
            this.getStudy().getUi().setMode("workbench");
          });
          break;
        case "study-menu-convert-to-standalone":
          control = new qx.ui.menu.Button().set({
            label: this.tr("Convert to Standalone"),
            icon: null,
          });
          control.addListener("execute", () => {
            this.getStudy().getUi().setMode("standalone");
          });
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
          optionsMenu.add(this.getChildControl("study-menu-convert-to-pipeline"));
          optionsMenu.add(this.getChildControl("study-menu-convert-to-standalone"));
          optionsMenu.add(this.getChildControl("study-menu-restore"));
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

        const convertToPipelineButton = this.getChildControl("study-menu-convert-to-pipeline");
        const convertToStandaloneButton = this.getChildControl("study-menu-convert-to-standalone");
        if (osparc.product.Utils.hasConvertToPipelineEnabled()) {
          study.getUi().bind("mode", convertToPipelineButton, "visibility", {
            converter: mode => mode === "standalone" ? "visible" : "excluded"
          });

          const evaluateConvertToStandaloneButton = () => {
            // exclude until we have the export to standalone backend functionality
            convertToStandaloneButton.exclude();
          };
          study.getWorkbench().addListener("pipelineChanged", () => evaluateConvertToStandaloneButton());
          study.getUi().addListener("changeMode", () => evaluateConvertToStandaloneButton());
        } else {
          convertToPipelineButton.exclude();
          convertToStandaloneButton.exclude();
        }

        const restoreButton = this.getChildControl("study-menu-restore");
        study.getUi().bind("mode", restoreButton, "visibility", {
          converter: mode => mode === "standalone" ? "visible" : "excluded"
        });

        const loggerButton = this.getChildControl("study-menu-open-logger");
        study.getUi().bind("mode", loggerButton, "visibility", {
          converter: mode => mode === "standalone" ? "visible" : "excluded"
        });
      } else {
        this.exclude();
      }
    }
  }
});
