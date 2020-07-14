/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Preferences page for managing the user's tags.
 */
qx.Class.define("osparc.desktop.preferences.pages.TagsPage", {
  extend: qx.ui.tabview.Page,
  construct: function() {
    this.base(arguments, null, "@FontAwesome5Solid/tags/24");
    this.setLayout(new qx.ui.layout.Grow());
    this.__container = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this.__container.set({
      backgroundColor: "material-button-background",
      paddingLeft: 10
    });
    const scroll = new qx.ui.container.Scroll(this.__container);
    this.add(scroll);
    this.__createComponents();
  },
  members: {
    __addTagButton: null,
    __tagItems: null,
    __createComponents: function() {
      this.__addTagButton = new qx.ui.form.Button(this.tr("Add new tag"), "@FontAwesome5Solid/plus-circle/14").set({
        appearance: "toolbar-md-button"
      });
      osparc.data.Resources.get("tags")
        .then(tags => {
          this.__tagItems = tags.map(tag => new osparc.component.form.tag.TagItem().set({...tag}));
          this.__renderLayout();
          this.__attachEventHandlers();
        })
        .catch(err => console.error(err));
    },
    __renderLayout: function() {
      this.__container.removeAll();
      // Print tag items
      this.__tagItems.forEach(tagItem => this.__container.add(tagItem));
      // New tag button
      const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignX: "center"
      }));
      buttonContainer.add(this.__addTagButton);
      this.__container.add(buttonContainer);
    },
    __attachEventHandlers: function() {
      this.__addTagButton.addListener("execute", () => {
        const itemCount = this.__container.getChildren().length;
        const newItem = new osparc.component.form.tag.TagItem().set({
          mode: osparc.component.form.tag.TagItem.modes.EDIT
        });
        this.__attachTagItemEvents(newItem);
        this.__container.addAt(newItem, Math.max(0, itemCount - 1));
      });
      this.__tagItems.forEach(tagItem => this.__attachTagItemEvents(tagItem));
    },
    __attachTagItemEvents: function(tagItem) {
      tagItem.addListener("cancelNewTag", e => {
        this.__container.remove(e.getTarget());
      }, this);
      tagItem.addListener("deleteTag", e => {
        this.__container.remove(e.getTarget());
      });
    }
  }
});
