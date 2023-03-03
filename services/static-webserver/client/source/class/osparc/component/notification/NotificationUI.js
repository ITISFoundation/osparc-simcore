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

qx.Class.define("osparc.component.notification.NotificationUI", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this.set({
      maxWidth: this.self().MAX_WIDTH,
      padding: this.self().PADDING,
      cursor: "pointer"
    });

    const layout = new qx.ui.layout.Grid(10, 2);
    layout.setColumnAlign(0, "center", "middle");
    layout.setColumnAlign(1, "left", "middle");
    layout.setColumnFlex(1, 1);
    this._setLayout(layout);

    this.getChildControl("icon");
    this.getChildControl("title");
    this.getChildControl("text");
    this.getChildControl("date");

    this.bind("read", this, "backgroundColor", {
      converter: read => read ? "background-main-3" : "background-main-4"
    });
  },

  properties: {
    id: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeId"
    },

    category: {
      check: ["new_organization", "study_shared", "template_shared"],
      init: null,
      nullable: false,
      event: "changeCategory"
    },

    actionablePath: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeActionablePath",
      apply: "__applyActionablePath"
    },

    title: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeTitle"
    },

    text: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeText"
    },

    date: {
      check: "Date",
      init: null,
      nullable: false,
      event: "changeDate"
    },

    read: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeRead"
    }
  },

  statics: {
    MAX_WIDTH: 300,
    PADDING: 10
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/paw/14",
            alignX: "center",
            alignY: "middle",
            minWidth: 18
          });
          this.bind("category", control, "source", {
            converter: value => {
              if (value === "new_organization") {
                return "@FontAwesome5Solid/users/14";
              } else if (value === "study_shared") {
                return "@FontAwesome5Solid/file/14";
              } else if (value === "new_organization") {
                return "@FontAwesome5Solid/copy/14";
              }
              return "";
            }
          });
          this._add(control, {
            row: 0,
            column: 0,
            rowSpan: 3
          });
          break;
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "text-13",
            rich: true,
            wrap: true
          });
          this.bind("title", control, "value");
          this._add(control, {
            row: 0,
            column: 1
          });
          break;
        case "text":
          control = new qx.ui.basic.Label().set({
            font: "text-12",
            rich: true,
            wrap: true
          });
          this.bind("text", control, "value");
          this._add(control, {
            row: 1,
            column: 1
          });
          break;
        case "date":
          control = new qx.ui.basic.Label().set({
            font: "text-11",
            rich: true,
            wrap: true
          });
          this.bind("date", control, "value", {
            converter: value => {
              if (value) {
                return osparc.utils.Utils.formatDateAndTime(new Date(value));
              }
              return "";
            }
          });
          this._add(control, {
            row: 2,
            column: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyActionablePath: function(value) {
      console.log("actionablePath", value);
    }
  }
});
