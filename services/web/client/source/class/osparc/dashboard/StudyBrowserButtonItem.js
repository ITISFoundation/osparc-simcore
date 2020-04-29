/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)

************************************************************************ */

/* eslint "qx-rules/no-refs-in-members": "warn" */

/**
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.dashboard.StudyBrowserButtonItem", {
  extend: osparc.dashboard.StudyBrowserButtonBase,

  construct: function() {
    this.base(arguments);

    // create a date format like "Oct. 19, 2018 11:31 AM"
    this.__dateFormat = new qx.util.format.DateFormat(
      qx.locale.Date.getDateFormat("medium")
    );
    this.__timeFormat = new qx.util.format.DateFormat(
      qx.locale.Date.getTimeFormat("short")
    );

    this.addListener("changeValue", e => {
      const val = this.getValue();

      const tick = this.getChildControl("tick-selected");
      tick.setVisibility(val ? "visible" : "excluded");

      const untick = this.getChildControl("tick-unselected");
      untick.setVisibility(val ? "excluded" : "visible");
    });
  },

  properties: {
    isTemplate: {
      check: "Boolean",
      nullable: false,
      init: false,
      event: "changeIsTemplate"
    },

    menu: {
      check: "qx.ui.menu.Menu",
      nullable: true,
      apply: "_applyMenu",
      event: "changeMenu"
    },

    uuid: {
      check: "String",
      apply: "_applyUuid"
    },

    studyTitle: {
      check: "String",
      apply: "_applyStudyTitle",
      nullable: true
    },

    studyDescription: {
      check: "String",
      apply: "_applyStudyDescription",
      nullable: true
    },

    creator: {
      check: "String",
      apply: "_applyCreator",
      nullable: true
    },

    lastChangeDate: {
      check: "Date",
      apply: "_applyLastChangeDate",
      nullable: true
    },

    tags: {
      check: "Array",
      apply: "_applyTags"
    }
  },

  statics: {
    menuButtonZIndex: 20
  },

  members: {
    __dateFormat: null,
    __timeFormat: null,

    multiSelection: function(on) {
      const menuButton = this.getChildControl("menu-button");
      menuButton.setVisibility(on ? "excluded" : "visible");
    },

    // overridden
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "menu-button":
          control = new qx.ui.form.MenuButton().set({
            width: 30,
            height: 30,
            icon: "@FontAwesome5Solid/ellipsis-v/16",
            zIndex: this.self().menuButtonZIndex,
            focusable: false
          });
          osparc.utils.Utils.setIdToWidget(control, "studyItemMenuButton");
          this._add(control, {
            top: 0,
            right: 0
          });
          break;
        case "tick-unselected":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/circle/16").set({
            zIndex: this.self().menuButtonZIndex -1
          });
          this._add(control, {
            top: 4,
            right: 4
          });
          break;
        case "tick-selected":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/check-circle/16").set({
            zIndex: this.self().menuButtonZIndex -1
          });
          this._add(control, {
            top: 4,
            right: 4
          });
          break;
        case "tags":
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(5, 3));
          this._mainLayout.addAt(control, 4);
          break;
      }

      return control || this.base(arguments, id);
    },

    _applyMenu: function(value, old) {
      const menuButton = this.getChildControl("menu-button");
      if (value) {
        menuButton.setMenu(value);
      }
      menuButton.setVisibility(value ? "visible" : "excluded");
    },

    _applyUuid: function(value, old) {
      osparc.utils.Utils.setIdToWidget(this, "studyBrowserListItem_"+value);
    },

    _applyStudyTitle: function(value, old) {
      const label = this.getChildControl("title");
      label.setValue(value);
      label.addListener("appear", () => {
        qx.event.Timer.once(() => {
          const labelDom = label.getContentElement().getDomElement();
          if (label.getMaxWidth() === parseInt(labelDom.style.width)) {
            label.setToolTipText(value);
          }
        }, this, 50);
      });
    },

    _applyStudyDescription: function(value, old) {
      if (value !== "" && this.getIsTemplate()) {
        const label = this.getChildControl("desc1");
        label.setValue(value);
      }
    },

    _applyLastChangeDate: function(value, old) {
      if (value && !this.getIsTemplate()) {
        const label = this.getChildControl("desc1");
        let dateStr = null;
        if (value.getDate() === (new Date()).getDate()) {
          dateStr = this.tr("Today");
        } else if (value.getDate() === (new Date()).getDate() - 1) {
          dateStr = this.tr("Yesterday");
        } else {
          dateStr = this.__dateFormat.format(value);
        }
        const timeStr = this.__timeFormat.format(value);
        label.setValue(dateStr + " " + timeStr);
      }
    },

    _applyCreator: function(value, old) {
      if (this.getIsTemplate()) {
        const label = this.getChildControl("desc2");
        label.setValue(value);
      }
    },

    _applyTags: function(tags) {
      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        const tagsContainer = this.getChildControl("tags");
        tagsContainer.removeAll();
        tags.forEach(tag => tagsContainer.add(new osparc.ui.basic.Tag(tag.name, tag.color, "studyBrowser")));
      }
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        const checks = [
          this.getStudyTitle(),
          this.getCreator()
        ];
        if (checks.filter(label => label.toLowerCase().trim().includes(data.text)).length == 0) {
          return true;
        }
      }
      if (data.tags && data.tags.length) {
        const tagNames = this.getTags().map(tag => tag.name);
        if (data.tags.filter(tag => tagNames.includes(tag)).length == 0) {
          return true;
        }
      }
      return false;
    }
  },

  destruct : function() {
    this.__dateFormat.dispose();
    this.__dateFormat = null;
    this.__timeFormat.dispose();
    this.__timeFormat = null;
  }
});
