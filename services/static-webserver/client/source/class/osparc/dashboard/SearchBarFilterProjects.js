/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.SearchBarFilterProjects", {
  extend: osparc.filter.UIFilter,

  construct: function(resourceType) {
    this.__resourceType = resourceType;

    this.base(arguments, "searchBarFilter-"+resourceType, "searchBarFilter");

    this._setLayout(new qx.ui.layout.VBox(8));

    this.set({
      backgroundColor: "input_background",
      padding: 8,
      decorator: "rounded",
    });

    this.__buildLayout();

    this.__currentFilter = null;

    qx.core.Init.getApplication().getRoot().add(this);

    this.__attachHideHandlers();
  },

  events: {
    "filterChanged": "qx.event.type.Data"
  },

  statics: {
    createToolbarRadioButton: function(label, icon, toolTipText = null, pos = null) {
      const rButton = new qx.ui.toolbar.RadioButton().set({
        label,
        icon,
        toolTipText,
        padding: 8,
        gap: 8,
        margin: 0,
      });
      rButton.getContentElement().setStyles({
        "border-radius": "0px"
      });
      if (pos === "left") {
        osparc.utils.Utils.addBorderLeftRadius(rButton);
      } else if (pos === "right") {
        osparc.utils.Utils.addBorderRightRadius(rButton);
      }
      return rButton;
    },
  },

  members: {
    __resourceType: null,
    __currentFilter: null,
    __filtersMenu: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "context-buttons":
          control = new qx.ui.toolbar.ToolBar().set({
            spacing: 0,
            padding: 0,
            backgroundColor: "input_background"
          });
          this._add(control);
          break;
        case "my-projects-button":
          control = this.self().createToolbarRadioButton(
            this.tr("My Projects"),
            "@FontAwesome5Solid/file/14",
            null,
            "left",
          );
          this.getChildControl("context-buttons").add(control);
          break;
        case "templates-button":
          control = this.self().createToolbarRadioButton(
            this.tr("Templates"),
            "@FontAwesome5Solid/copy/14",
          );
          this.getChildControl("context-buttons").add(control);
          break;
        case "public-projects-button":
          control = this.self().createToolbarRadioButton(
            this.tr("My Projects"),
            "@FontAwesome5Solid/globe/14",
            null,
            "right",
          );
          this.getChildControl("context-buttons").add(control);
          break;
        case "search-bar":
          control = new osparc.dashboard.SearchBarFilter(this.__resourceType);
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      const radioGroup = new qx.ui.form.RadioGroup();
      const myProjectsButton = this.getChildControl("my-projects-button");
      const templatesButton = this.getChildControl("templates-button");
      const publicProjectsButton = this.getChildControl("public-projects-button");
      const searchBar = this.getChildControl("search-bar");
      searchBar.set({
        showFilterMenu: false,
      });

      radioGroup.add(myProjectsButton, templatesButton, publicProjectsButton);
    },

    __attachHideHandlers: function() {
      const tapListener = e => {
        if (osparc.utils.Utils.isMouseOnElement(this, e)) {
          return;
        }
        this.exclude();
        document.removeEventListener("mousedown", tapListener);
      };;
      document.addEventListener("mousedown", tapListener);
    },
  }
});
