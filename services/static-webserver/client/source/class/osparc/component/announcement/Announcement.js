/* ************************************************************************

  osparc - the simcore frontend

  https://osparc.io

  Copyright:
    2018 IT'IS Foundation, https://itis.swiss

  License:
    MIT: https://opensource.org/licenses/MIT

  Authors:
    * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.announcement.Announcement", {
  extend: qx.core.Object,

  construct: function(announcementData) {
    this.base(arguments);

    this.set({
      id: announcementData.id,
      products: announcementData.products,
      start: new Date(announcementData.start),
      end: new Date(announcementData.end),
      title: announcementData.title,
      description: announcementData.description,
      link: announcementData.link,
      widgets: announcementData.widgets
    });
  },

  properties: {
    id: {
      check: "String",
      init: null,
      nullable: false
    },

    products: {
      check: "Array",
      init: [],
      nullable: false
    },

    start: {
      check: "Date",
      init: null,
      nullable: false
    },

    end: {
      check: "Date",
      init: null,
      nullable: false
    },

    title: {
      check: "String",
      init: null,
      nullable: true
    },

    description: {
      check: "String",
      init: null,
      nullable: true
    },

    link: {
      check: "String",
      init: null,
      nullable: true
    },

    widgets: {
      check: "Array",
      init: [],
      nullable: true
    }
  }
});
