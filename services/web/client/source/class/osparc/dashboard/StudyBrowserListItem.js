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

qx.Class.define("osparc.dashboard.StudyBrowserListItem", {
  extend: osparc.dashboard.StudyBrowserListBase,

  construct: function() {
    this.base(arguments);

    // create a date format like "Oct. 19, 2018 11:31 AM"
    this.__dateFormat = new qx.util.format.DateFormat(
      qx.locale.Date.getDateFormat("medium")
    );
    this.__timeFormat = new qx.util.format.DateFormat(
      qx.locale.Date.getTimeFormat("short")
    );

    const tickIcon = this.getChildControl("tick-selected");
    this.bind("value", tickIcon, "visibility", {
      converter: function(value) {
        return value ? "visible" : "excluded";
      }
    });
  },

  properties: {
    menu: {
      check : "qx.ui.menu.Menu",
      nullable : true,
      apply : "_applyMenu",
      event : "changeMenu"
    },

    uuid: {
      check: "String",
      apply : "_applyUuid"
    },

    studyTitle: {
      check: "String",
      apply : "_applyStudyTitle",
      nullable : true
    },

    creator: {
      check: "String",
      apply : "_applyCreator",
      nullable : true
    },

    lastChangeDate: {
      check : "Date",
      apply : "_applylastChangeDate",
      nullable : true
    },

    tags: {
      check: "Array",
      apply: "_applyTags"
    }
  },

  members: {
    __dateFormat: null,
    __timeFormat: null,

    // overridden
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "menu-button":
          control = new qx.ui.form.MenuButton().set({
            width: 30,
            height: 30,
            icon: "@FontAwesome5Solid/ellipsis-v/16",
            focusable: false,
            zIndex: 20
          });
          this._add(control, {
            top: 0,
            right: 0
          });
          break;
        case "tick-selected":
          control = new qx.ui.form.MenuButton().set({
            width: 30,
            height: 30,
            icon: "@FontAwesome5Solid/check-circle/16",
            focusable: false,
            zIndex: 21
          });
          this._add(control, {
            top: 0,
            right: 0
          });
          break;
        case "studyTitle":
          control = new qx.ui.basic.Label(this.getStudyTitle()).set({
            margin: [5, 0],
            font: "title-14",
            anonymous: true
          });
          osparc.utils.Utils.setIdToWidget(control, "studyBrowserListItem_title");
          this._mainLayout.addAt(control, 0);
          break;
        case "creator":
          control = new qx.ui.basic.Label(this.getCreator()).set({
            rich: true,
            allowGrowY: false,
            anonymous: true
          });
          osparc.utils.Utils.setIdToWidget(control, "studyBrowserListItem_creator");
          this._mainLayout.addAt(control, 1);
          break;
        case "lastChangeDate":
          control = new qx.ui.basic.Label().set({
            rich: true,
            allowGrowY: false,
            anonymous: true
          });
          osparc.utils.Utils.setIdToWidget(control, "studyBrowserListItem_lastChangeDate");
          this._mainLayout.addAt(control, 2);
          break;
        case "icon":
          control = new qx.ui.basic.Image(this.getIcon()).set({
            anonymous: true,
            scale: true,
            allowStretchX: true,
            allowStretchY: true,
            height: 120
          });
          this._mainLayout.addAt(control, 3);
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

    _applyIcon: function(value, old) {
      let icon = this.getChildControl("icon");
      icon.set({
        source: value,
        paddingTop: value && value.match(/^@/) ? 30 : 0
      });
    },

    _applyStudyTitle: function(value, old) {
      let label = this.getChildControl("studyTitle");
      label.setValue(value);
    },

    _applyCreator: function(value, old) {
      let label = this.getChildControl("creator");
      label.setValue(value);
    },

    _applylastChangeDate: function(value, old) {
      let label = this.getChildControl("lastChangeDate");
      if (value) {
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
      } else {
        label.resetValue();
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
