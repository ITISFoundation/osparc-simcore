/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.desktop.credits.DateFilters", {
  extend: qx.ui.core.Widget,

  construct() {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(7));
    this._buildLayout();
  },

  events: {
    "change": "qx.event.type.Data"
  },

  members: {
    _buildLayout() {
      this._removeAll();

      const defaultFrom = new Date();
      // Range defaults
      // from last 24h...
      defaultFrom.setDate(defaultFrom.getDate() - 1);
      // .. to now
      const defaultTo = new Date();

      this.__from = this.__addDateInput("From", defaultFrom);
      this.__until = this.__addDateInput("Until", defaultTo);

      const lastDayBtn = new qx.ui.form.Button("Last 24h").set({
        allowStretchY: false,
        alignY: "bottom"
      });
      lastDayBtn.addListener("execute", () => {
        const today = new Date();
        const last24h = new Date(today);
        last24h.setDate(today.getDate() - 1);
        this.__from.setValue(last24h);
        this.__until.setValue(today);
      });
      this._add(lastDayBtn);

      const lastWeekBtn = new qx.ui.form.Button("Last week").set({
        allowStretchY: false,
        alignY: "bottom"
      });
      lastWeekBtn.addListener("execute", () => {
        const today = new Date();
        const lastWeek = new Date(today);
        lastWeek.setDate(today.getDate() - 7)
        this.__from.setValue(lastWeek);
        this.__until.setValue(today);
      });
      this._add(lastWeekBtn);

      const lastMonthBtn = new qx.ui.form.Button("Last month").set({
        allowStretchY: false,
        alignY: "bottom"
      });
      lastMonthBtn.addListener("execute", () => {
        const today = new Date();
        const lastMonth = new Date(today);
        lastMonth.setMonth(today.getMonth() - 1);
        this.__from.setValue(lastMonth);
        this.__until.setValue(today);
      });
      this._add(lastMonthBtn);

      const lastYearBtn = new qx.ui.form.Button("Last year").set({
        allowStretchY: false,
        alignY: "bottom"
      });
      lastYearBtn.addListener("execute", () => {
        const today = new Date();
        const lastYear = new Date(today);
        lastYear.setYear(today.getFullYear() - 1);
        this.__from.setValue(lastYear);
        this.__until.setValue(today);
      })
      this._add(lastYearBtn);
    },

    __addDateInput(label, initDate) {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      const lbl = new qx.ui.basic.Label(label);
      container.add(lbl);
      const datepicker = new qx.ui.form.DateField();
      datepicker.setValue(initDate ? initDate : new Date());
      datepicker.addListener("changeValue", e => this._changeHandler(e));
      container.add(datepicker);
      this._add(container);
      return datepicker;
    },

    _changeHandler(e) {
      const timestampFrom = this.__from.getValue().getTime();
      const timestampUntil = this.__until.getValue().getTime();
      if (timestampFrom > timestampUntil) {
        // 'From' date must be before 'until'
        if (e.getCurrentTarget() === this.__from) {
          // Adapt the date the user did not change
          this.__until.setValue(new Date(this.__from.getValue().getTime()));
        } else {
          this.__from.setValue(new Date(this.__until.getValue().getTime()));
        }
        return;
      }
      const from = osparc.utils.Utils.formatDateYyyyMmDd(this.__from.getValue());
      const until = osparc.utils.Utils.formatDateYyyyMmDd(this.__until.getValue());
      this.fireDataEvent("change", {
        from,
        until
      });
    },

    getValue() {
      const from = osparc.utils.Utils.formatDateYyyyMmDd(this.__from.getValue())
      const until = osparc.utils.Utils.formatDateYyyyMmDd(this.__until.getValue())
      return {
        from,
        until
      }
    }
  }
});
