/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that shows a date followed by "by (user_icon)"
 */
qx.Class.define("osparc.ui.basic.DateAndBy", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(5));

    this.set({
      alignY: "middle",
    });
  },

  properties: {
    date: {
      check: "Date",
      nullable: true,
      apply: "__applyDate",
    },

    groupId: {
      check: "Number",
      nullable: true,
      apply: "__applyGroupId",
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "date-text":
          control = new qx.ui.basic.Label().set({
            textColor: "contrasted-text-dark",
            alignY: "middle",
            rich: true,
            font: "text-12",
            allowGrowY: false
          });
          this._addAt(control, 0);
          break;
        case "last-touching":
          control = new qx.ui.basic.Atom().set({
            alignY: "middle",
            allowGrowX: false,
            allowShrinkX: false,
            label: "by",
            font: "text-12",
            icon: osparc.dashboard.CardBase.SHARED_USER,
            iconPosition: "right",
          });
          this._addAt(control, 1);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyDate: function(value) {
      if (value) {
        const label = this.getChildControl("date-text");
        const today = new Date();
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        if (today.toDateString() === value.toDateString()) {
          label.setValue(osparc.utils.Utils.formatDateAndTime(value)); // show date and time
        } else if (yesterday.toDateString() === value.toDateString()) {
          label.setValue(osparc.utils.Utils.formatDateAndTime(value)); // show date and time
        } else {
          label.setValue(osparc.utils.Utils.formatDate(value)); // show date only
        }
      }
    },

    __applyGroupId: function(groupId) {
      if (groupId) {
        const atom = this.getChildControl("last-touching");
        const myGroupId = osparc.auth.Data.getInstance().getGroupId();
        if (groupId === myGroupId) {
          atom.setLabel("by me");
        } else {
          atom.setLabel("by");
          osparc.dashboard.CardBase.addHintFromGids(atom, [groupId]);
        }
      }
    },
  }
});
