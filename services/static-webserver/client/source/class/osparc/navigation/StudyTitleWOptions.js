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
    "downloadStudyLogs": "qx.event.type.Event"
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
        case "study-menu-download-logs":
          control = new qx.ui.menu.Button().set({
            label: this.tr("Download logs"),
            icon: "@FontAwesome5Solid/download/14"
          });
          control.addListener("execute", () => this.fireEvent("downloadStudyLogs"));
          break;
        case "study-menu-button": {
          const optionsMenu = new qx.ui.menu.Menu();
          optionsMenu.add(this.getChildControl("study-menu-info"));
          optionsMenu.add(this.getChildControl("study-menu-download-logs"));
          control = new qx.ui.form.MenuButton().set({
            appearance: "fab-button",
            menu: optionsMenu,
            icon: "@FontAwesome5Solid/ellipsis-v/14",
            allowGrowY: false
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

    __applyStudy: function(study) {
      if (study) {
        study.bind("name", this.getChildControl("edit-title-label"), "value");
      } else {
        this.exclude();
      }
    }
  }
});
