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
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/tags/24";
    const title = this.tr("Tags");
    this.base(arguments, title, iconSrc);

    const studiesLabel = osparc.product.Utils.getStudyAlias({plural: true});
    const studyLabel = osparc.product.Utils.getStudyAlias();
    const msg = this.tr("\
    Tags are annotations to help users with grouping ") + studiesLabel + this.tr(" in the Dashboard. \
    Once the tags are created, they can be assigned to the ") + studyLabel + this.tr("  via 'More options...' on the ") + studyLabel + this.tr(" cards.");
    const intro = this._createHelpLabel(msg);
    this._add(intro);

    this._add(new qx.ui.core.Spacer(null, 10));

    this.__container = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this.__container.set({
      backgroundColor: "background-main-2",
      paddingLeft: 10
    });
    const scroll = new qx.ui.container.Scroll(this.__container);
    this.add(scroll);

    this.__createComponents();
  },

  members: {
    __container: null,
    __addTagButton: null,
    __tagItems: null,

    __createComponents: function() {
      this.__addTagButton = new qx.ui.form.Button().set({
        appearance: "strong-button",
        label: this.tr("New Tag"),
        icon: "@FontAwesome5Solid/plus/14"
      });
      osparc.utils.Utils.setIdToWidget(this.__addTagButton, "addTagBtn");
      osparc.data.Resources.get("tags")
        .then(tags => {
          this.__tagItems = tags.map(tag => new osparc.form.tag.TagItem().set({...tag}));
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
      buttonContainer.add(new qx.ui.core.Spacer(null, 10));
      buttonContainer.add(this.__addTagButton);
      this.__container.add(buttonContainer);
    },

    __attachEventHandlers: function() {
      this.__addTagButton.addListener("execute", () => {
        const itemCount = this.__container.getChildren().length;
        const newItem = new osparc.form.tag.TagItem().set({
          mode: osparc.form.tag.TagItem.modes.EDIT
        });
        this.__attachTagItemEvents(newItem);
        this.__container.addAt(newItem, Math.max(0, itemCount - 1));
      });
      this.__tagItems.forEach(tagItem => this.__attachTagItemEvents(tagItem));
    },

    __attachTagItemEvents: function(tagItem) {
      tagItem.addListener("cancelNewTag", e => this.__container.remove(e.getTarget()), this);
      tagItem.addListener("deleteTag", e => this.__container.remove(e.getTarget()));
    }
  }
});
