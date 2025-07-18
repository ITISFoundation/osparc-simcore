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

qx.Class.define("osparc.dashboard.SearchBarFilterExtended", {
  extend: qx.ui.core.Widget,

  construct: function(sourceSearchBarFilter, resourceType) {
    this.__sourceSearchBarFilter = sourceSearchBarFilter;
    this.__resourceType = resourceType;

    this.base(arguments, "searchBarFilter-"+resourceType, "searchBarFilter");

    this._setLayout(new qx.ui.layout.VBox(10));

    this.set({
      backgroundColor: osparc.dashboard.SearchBarFilter.BG_COLOR,
      padding: 8,
      decorator: "rounded",
    });

    this.__buildLayout();

    this.__searchMyProjectsSelected();

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
    __sourceSearchBarFilter: null,
    __resourceType: null,
    __currentFilter: null,
    __filtersMenu: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "search-bar-filter":
          control = new osparc.dashboard.SearchBarFilter(this.__resourceType);
          control.getChildControl("text-field").addListener("appear", () => {
            control.getChildControl("text-field").focus();
            control.getChildControl("text-field").activate();
          });
          this._add(control);
          break;
        case "context-buttons":
          control = new qx.ui.toolbar.ToolBar().set({
            spacing: 0,
            padding: 0,
            backgroundColor: osparc.dashboard.SearchBarFilter.BG_COLOR,
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
        case "filter-buttons":
          control = new qx.ui.toolbar.ToolBar().set({
            backgroundColor: osparc.dashboard.SearchBarFilter.BG_COLOR,
          });
          this._add(control);
          break;
        case "shared-with-button":
          control = new qx.ui.toolbar.MenuButton(this.tr("Shared with"), "@FontAwesome5Solid/share-alt/12");
          this.__addSharedWithMenu(control);
          this.getChildControl("filter-buttons").add(control);
          break;
        case "tags-button":
          control = new qx.ui.toolbar.MenuButton(this.tr("Tags"), "@FontAwesome5Solid/tags/12");
          this.__addTagsMenu(control);
          this.getChildControl("filter-buttons").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("search-bar-filter").set({
        showFilterMenu: false,
      });

      const textField = this.getChildControl(("search-bar-filter")).getChildControl("text-field");
      textField.addListener("keypress", e => {
        if (e.getKeyIdentifier() === "Enter") {
          this.__sourceSearchBarFilter.getChildControl("text-field").setValue(textField.getValue());
          this.exclude();
        }
      }, this);
      textField.addListener("changeValue", () => {
        this.__sourceSearchBarFilter.getChildControl("text-field").setValue(textField.getValue());
        this.exclude();
      }, this);

      const resetButton = this.getChildControl("search-bar-filter").getChildControl("reset-button");
      resetButton.set({
        paddingRight: 2, // 10-8
        opacity: 0.7,
        backgroundColor: "transparent",
      });
      osparc.utils.Utils.hideBorder(resetButton);
      resetButton.addListener("tap", () =>{
        this.exclude();
      });

      const radioGroup = new qx.ui.form.RadioGroup();
      const myProjectsButton = this.getChildControl("my-projects-button");
      const templatesButton = this.getChildControl("templates-button");
      const publicProjectsButton = this.getChildControl("public-projects-button");
      radioGroup.add(myProjectsButton, templatesButton, publicProjectsButton);
      myProjectsButton.addListener("changeValue", this.__searchMyProjectsSelected, this);
      templatesButton.addListener("changeValue", this.__searchTemplatesSelected, this);
      publicProjectsButton.addListener("changeValue", this.__searchPublicProjectsSelected, this);
    },

    __searchMyProjectsSelected: function() {
      this.getChildControl("search-bar-filter").getChildControl("text-field").setPlaceholder(this.tr("Search in My projects"));

      this.getChildControl("shared-with-button").setVisibility("visible");
      this.getChildControl("tags-button").setVisibility("visible");
    },

    __searchTemplatesSelected: function() {
      this.getChildControl("search-bar-filter").getChildControl("text-field").setPlaceholder(this.tr("Search in Templates"));

      this.getChildControl("shared-with-button").setVisibility("excluded");
      this.getChildControl("tags-button").setVisibility("visible");
    },

    __searchPublicProjectsSelected: function() {
      this.getChildControl("search-bar-filter").getChildControl("text-field").setPlaceholder(this.tr("Search in Public projects"));

      this.getChildControl("shared-with-button").setVisibility("excluded");
      this.getChildControl("tags-button").setVisibility("visible");
    },

    __addSharedWithMenu: function(menuButton) {
      const menu = this.__sharedWithMenu = new qx.ui.menu.Menu();

      const sharedWithRadioGroup = new qx.ui.form.RadioGroup();
      const options = osparc.dashboard.SearchBarFilter.getSharedWithOptions(this.__resourceType);
      options.forEach((option, idx) => {
        const button = new qx.ui.menu.RadioButton(option.label);
        menu.add(button);
        button.addListener("execute", () => {
          this.__sourceSearchBarFilter.setSharedWithActiveFilter(option.id, option.label);
          this.exclude();
        });
        sharedWithRadioGroup.add(button);
        // preselect show-all
        if (idx === 0) {
          sharedWithRadioGroup.setSelection([button]);
        }
      });
      menuButton.setMenu(menu);
    },

    __addTagsMenu: function(menuButton) {
      const tags = osparc.store.Tags.getInstance().getTags();
      menuButton.setVisibility(tags.length ? "visible" : "excluded");
      if (tags.length) {
        const menu = this.__tagsMenu = new qx.ui.menu.Menu();
        osparc.utils.Utils.setIdToWidget(menu, "searchBarFilter-tags-menu");
        tags.forEach(tag => {
          const tagButton = new qx.ui.menu.Button(tag.getName(), "@FontAwesome5Solid/tag/12");
          tagButton.getChildControl("icon").setTextColor(tag.getColor());
          menu.add(tagButton);
          tagButton.addListener("execute", () => {
            this.__sourceSearchBarFilter.addTagActiveFilter(tag);
            this.exclude();
          });
        });
        menuButton.setMenu(menu);
      }
    },

    __attachHideHandlers: function() {
      const tapListener = e => {
        const excludeElements = [
          this,
          this.__sharedWithMenu,
          this.__tagsMenu,
        ];
        for (let i=0; i<excludeElements.length; i++) {
          if (osparc.utils.Utils.isMouseOnElement(excludeElements[i], e)) {
            return;
          }
        }

        this.exclude();
        document.removeEventListener("mousedown", tapListener);
      };;
      document.addEventListener("mousedown", tapListener);
    },
  }
});
