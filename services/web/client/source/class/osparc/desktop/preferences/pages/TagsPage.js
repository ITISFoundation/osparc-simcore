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
    this.setLayout(new qx.ui.layout.VBox(10));
    this.__createComponents();
    this.__renderLayout();
    this.__attachEventHandlers();
  },
  members: {
    __addTagButton: null,
    __createComponents: function() {
      this.__addTagButton = new qx.ui.form.Button(this.tr("Add new tag"), "@FontAwesome5Solid/plus-circle/14").set({
        appearance: "md-button"
      });
    },
    __renderLayout: function() {
      this.removeAll();
      // Print tag items
      tags.map(tag =>this.add(new osparc.component.form.tag.TagItem().set({...tag})));
      // New tag button
      const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignX: "right"
      }));
      buttonContainer.add(this.__addTagButton);
      this.add(buttonContainer);
    },
    __attachEventHandlers: function() {
      this.__addTagButton.addListener("execute", () => {
        this.add(new osparc.component.form.tag.TagItem().set({
          mode: osparc.component.form.tag.TagItem.modes.EDIT
        }));
      });
    }
  }
});

const tags = [
  {
    id: 1,
    name: "shared code",
    description: "This is a description for the tag",
    color: "#523390"
  },
  {
    id: 2,
    name: "shaaah",
    description: "This is a description for the tag",
    color: "#121200"
  },
  {
    id: 3,
    name: "zumzum",
    description: "This is a description for the tag",
    color: "#abcdef"
  },
  {
    id: 4,
    name: "zumzum",
    description: "This is a description for the tag",
    color: "#14558a"
  },
  {
    id: 5,
    name: "zumzumzum",
    description: "This is a description for the tag",
    color: "#af550a"
  },
  {
    id: 6,
    name: "kaboom",
    description: "This is a description for the tag",
    color: "#2388f1"
  },
  {
    id: 7,
    name: "a new tag pt 2",
    description: "This is a description for the tag, just a bit longer",
    color: "#123456"
  },
  {
    id: 8,
    name: "have you ever",
    description: "This is a description for the tag",
    color: "#875421"
  },
  {
    id: 9,
    name: "postpro",
    description: "This is a description for the tag",
    color: "#fedcba"
  }
]