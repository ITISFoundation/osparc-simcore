/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.filter.DateFilters", {
  extend: qx.ui.core.Widget,

  construct() {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(6));

    this._add(this.getChildControl("range"));
    this._add(this.getChildControl("from"));
    this._add(this.getChildControl("until"));

    // initialize to default (Last 7 days)
    const selectbox = this.getChildControl("range").getUserData("selectbox");
    selectbox.setSelection([selectbox.getSelectables()[1]]); // "last_7_days"
  },

  events: {
    "change": "qx.event.type.Data",
  },

  statics: {
    RANGES: {
      TODAY: {
        id: "today",
        label: "Today",
      },
      LAST_7_DAYS: {
        id: "last_7_days",
        label: "Last 7 days",
      },
      LAST_30_DAYS: {
        id: "last_30_days",
        label: "Last 30 days",
      },
      LAST_YEAR: {
        id: "last_year",
        label: "Last year",
      },
      CUSTOM: {
        id: "custom",
        label: "Custom",
      },
    },
  },

  members: {
    _createChildControlImpl(id, hash) {
      let control;
      switch (id) {
        case "range": {
          const container = new qx.ui.container.Composite(new qx.ui.layout.HBox(2));
          container.add(new qx.ui.basic.Label(this.tr("Time Range")));
          const select = new qx.ui.form.SelectBox().set({ allowStretchY: false });
          Object.values(this.self().RANGES).forEach(({ id, label }) => {
            const item = new qx.ui.form.ListItem(label);
            item.setModel(id);
            select.add(item);
          });
          select.addListener("changeSelection", () => {
            const model = select.getSelection()[0].getModel();
            this.__applyFilter(model);
          });
          container.add(select, { flex: 1 });
          control = container;
          control.setUserData("selectbox", select);
          break;
        }
        case "from": {
          const c = new qx.ui.container.Composite(new qx.ui.layout.HBox(2));
          c.add(new qx.ui.basic.Label("From"));
          c.add(this.getChildControl("from-datefield"));
          control = c;
          break;
        }
        case "until": {
          const c = new qx.ui.container.Composite(new qx.ui.layout.HBox(2));
          c.add(new qx.ui.basic.Label("Until"));
          c.add(this.getChildControl("until-datefield"));
          control = c;
          break;
        }
        case "from-datefield": {
          const df = new qx.ui.form.DateField();
          df.setValue(new Date());
          df.addListener("changeValue", e => this.__onDateChange(e));
          control = df;
          break;
        }
        case "until-datefield": {
          const df = new qx.ui.form.DateField();
          df.setValue(new Date());
          df.addListener("changeValue", e => this.__onDateChange(e));
          control = df;
          break;
        }
      }

      return control || this.base(arguments, id, hash);
    },

    __applyFilter(filterId) {
      const fromContainer = this.getChildControl("from");
      const untilContainer = this.getChildControl("until");
      const fromField = this.getChildControl("from-datefield");
      const untilField = this.getChildControl("until-datefield");

      const isCustom = filterId === this.self().RANGES.CUSTOM.id;
      fromContainer.setVisibility(isCustom ? "visible" : "excluded");
      untilContainer.setVisibility(isCustom ? "visible" : "excluded");

      if (!isCustom) {
        const { from, until } = this.__computeRange(filterId);
        fromField.setValue(from);
        untilField.setValue(until);
      }

      this.fireDataEvent("change", this.getValue());
    },

    __computeRange(filterId) {
      const today = this.__startOfDay(new Date());
      let from = new Date(today);
      let until = new Date(today);

      switch (filterId) {
        case this.self().RANGES.TODAY.id:
          break;

        case this.self().RANGES.LAST_7_DAYS.id:
          from.setDate(today.getDate() - 7);
          break;

        case this.self().RANGES.LAST_30_DAYS.id:
          from.setDate(today.getDate() - 30);
          break;

        case this.self().RANGES.LAST_YEAR.id:
          from.setFullYear(today.getFullYear() - 1);
          break;

        case this.self().RANGES.CUSTOM.id:
        default:
          from = this.getChildControl("from-datefield").getValue() || from;
          until = this.getChildControl("until-datefield").getValue() || until;
          break;
      }

      return { from, until };
    },

    __startOfDay(d) {
      const nd = new Date(d);
      nd.setHours(0, 0, 0, 0);
      return nd;
    },

    __onDateChange(e) {
      const select = this.getChildControl("range").getUserData("selectbox");
      const filterId = select.getSelection()[0].getModel();
      const isCustom = filterId === this.self().RANGES.CUSTOM.id;

      if (!isCustom) return;

      const fromField = this.getChildControl("from-datefield");
      const untilField = this.getChildControl("until-datefield");
      const fromDate = fromField.getValue();
      const untilDate = untilField.getValue();

      if (!fromDate || !untilDate) return;

      if (fromDate.getTime() > untilDate.getTime()) {
        if (e.getCurrentTarget() === fromField) {
          untilField.setValue(new Date(fromDate.getTime()));
        } else {
          fromField.setValue(new Date(untilDate.getTime()));
        }
      }

      this.fireDataEvent("change", this.getValue());
    },

    getValue() {
      const selectbox = this.getChildControl("range").getUserData("selectbox");
      const filterId = selectbox.getSelection()[0].getModel();
      const { from, until } = this.__computeRange(filterId);

      return {
        filter: filterId,
        from: osparc.utils.Utils.formatDateYyyyMmDd(from),
        until: osparc.utils.Utils.formatDateYyyyMmDd(until)
      };
    },
  },
});
