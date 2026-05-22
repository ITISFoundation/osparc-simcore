/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.support.Conversations", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));
    this.__conversationListItems = [];

    this.__filterButtons = [];
    this.__filterButtons.push(this.getChildControl("filter-all-button"));
    this.__filterButtons.push(this.getChildControl("filter-unread-button"));
    if (osparc.store.Groups.getInstance().amIASupportUser()) {
      this.__filterButtons.push(this.getChildControl("filter-active-button"));
      this.__filterButtons.push(this.getChildControl("filter-archived-button"));
    }

    this.__fetchConversationCounts();
    this.__fetchConversations(this.getCurrentFilter());

    this.__listenToNewConversations();
    this.__listenToConversationDeleted();
  },

  properties: {
    currentFilter: {
      check: [
        "all",
        "unread",
        "active",
        "archived",
      ],
      init: "all",
      event: "changeCurrentFilter",
      apply: "__applyCurrentFilter",
    },
  },

  events: {
    "openConversation": "qx.event.type.Data",
  },

  statics: {
    FILTER_BUTTON_AESTHETIC: {
      appearance: "filter-toggle-button",
      allowGrowX: false,
      paddingTop: 4,
      paddingBottom: 4,
    },
  },

  members: {
    __conversationListItems: null,
    __totalConversations: null,
    __isFetchingMore: false,
    __fetchRequestId: 0,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "filters-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(4));
          this._addAt(control, 0);
          break;
        case "filter-all-button":
          control = new qx.ui.form.ToggleButton(this.tr("All"));
          control.set({
            value: true,
            toolTipText: this.tr("Show all conversations"),
            ...this.self().FILTER_BUTTON_AESTHETIC,
          });
          control.addListener("execute", () => this.setCurrentFilter("all"));
          this.getChildControl("filters-layout").add(control);
          break;
        case "filter-unread-button":
          control = new qx.ui.form.ToggleButton(this.tr("Unread"));
          control.set({
            toolTipText: this.tr("Show only unread conversations"),
            ...this.self().FILTER_BUTTON_AESTHETIC,
          });
          control.addListener("execute", () => this.setCurrentFilter("unread"));
          this.getChildControl("filters-layout").add(control);
          break;
        case "filter-active-button":
          control = new qx.ui.form.ToggleButton(this.tr("Active"));
          control.set({
            toolTipText: this.tr("Show only active (unarchived) conversations"),
            ...this.self().FILTER_BUTTON_AESTHETIC,
          });
          control.addListener("execute", () => this.setCurrentFilter("active"));
          this.getChildControl("filters-layout").add(control);
          break;
        case "filter-archived-button":
          control = new qx.ui.form.ToggleButton(this.tr("Archived"));
          control.set({
            toolTipText: this.tr("Show only archived conversations"),
            ...this.self().FILTER_BUTTON_AESTHETIC,
          });
          control.addListener("execute", () => this.setCurrentFilter("archived"));
          this.getChildControl("filters-layout").add(control);
          break;
        case "loading-button":
          control = new osparc.ui.form.FetchButton();
          this._addAt(control, 1);
          break;
        case "no-messages-label":
          control = new qx.ui.basic.Label().set({
            alignX: "center",
            visibility: "excluded",
          });
          this._addAt(control, 2);
          break;
        case "scroll-container":
          control = new qx.ui.container.Scroll();
          control.getChildControl("pane").addListener("scrollY", () => this.__onScroll(), this);
          this._addAt(control, 3, {
            flex: 1
          });
          break;
        case "conversations-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.getChildControl("scroll-container").add(control);
          break;
        case "loading-spinner":
          control = new osparc.ui.form.FetchButton(this.tr("Loading more...")).set({
            alignX: "center",
            visibility: "excluded",
          });
          control.setFetching(true);
          break;
      }

      return control || this.base(arguments, id);
    },

    __applyCurrentFilter: function(filter) {
      this.getChildControl("no-messages-label").exclude();
      this.__highlightCurrentFilter(filter);
      this.__clearConversationsList();
      this.__fetchConversations(filter);
    },

    __clearConversationsList: function() {
      this.__conversationListItems = [];
      this.__totalConversations = null;
      this.__isFetchingMore = false;
      this.getChildControl("conversations-layout").removeAll();
    },

    __highlightCurrentFilter: function(filter) {
      this.__filterButtons.forEach(button => button.setValue(false));
      switch (filter) {
        case "all":
          this.getChildControl("filter-all-button").setValue(true);
          break;
        case "unread":
          this.getChildControl("filter-unread-button").setValue(true);
          break;
        case "active":
          this.getChildControl("filter-active-button").setValue(true);
          break;
        case "archived":
          this.getChildControl("filter-archived-button").setValue(true);
          break;
      }
    },

    __updateBadgesVisibility: function(filter) {
      this.__conversationListItems.forEach(conversationItem => {
        conversationItem.getChildControl("badges-layout").setVisibility(filter === "all" ? "visible" : "excluded");
      });
    },

    __showNoMessagesLabelIfNeeded: function(filter) {
      const hasVisibleConversations = this.__conversationListItems.some(conversationItem => conversationItem.isVisible());
      if (!hasVisibleConversations) {
        let msg = "";
        switch (filter) {
          case "all":
            msg = this.tr("No conversations yet");
            break;
          case "unread":
            msg = this.tr("No unread conversations");
            break;
          case "active":
            msg = this.tr("No active conversations");
            break;
          case "archived":
            msg = this.tr("No archived conversations");
            break;
        }
        this.getChildControl("no-messages-label").set({
          value: msg,
          visibility: "visible",
        });
      }
    },

    __getConversationItem: function(conversationId) {
      return this.__conversationListItems.find(conversation => conversation.getConversation().getConversationId() === conversationId);
    },

    __fetchConversationCounts: function() {
      osparc.store.ConversationsSupport.getInstance().fetchConversationCounts()
        .then(counts => {
          if (counts.all !== undefined) {
            this.getChildControl("filter-all-button").setLabel(this.tr("All") + ` (${counts.all})`);
          }
          if (counts.unread !== undefined) {
            this.getChildControl("filter-unread-button").setLabel(this.tr("Unread") + ` (${counts.unread})`);
          }
          if (counts.active !== undefined) {
            this.getChildControl("filter-active-button").setLabel(this.tr("Active") + ` (${counts.active})`);
          }
          if (counts.archived !== undefined) {
            this.getChildControl("filter-archived-button").setLabel(this.tr("Archived") + ` (${counts.archived})`);
          }
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __fetchConversations: function(filter) {
      const loadMoreButton = this.getChildControl("loading-button");
      loadMoreButton.setFetching(true);

      const requestId = ++this.__fetchRequestId;
      osparc.store.ConversationsSupport.getInstance().fetchConversations(filter)
        .then(resp => {
          if (requestId !== this.__fetchRequestId) {
            return;
          }
          if (resp && resp.conversations && resp.conversations.length) {
            resp.conversations.forEach(conversation => this.__addConversation(conversation));
          }
          this.__totalConversations = resp ? resp.total : null;
          this.__sortConversations();
          this.__updateBadgesVisibility(filter);
          this.__updateLoadingSpinner();
        })
        .finally(() => {
          if (requestId !== this.__fetchRequestId) {
            return;
          }
          loadMoreButton.setFetching(false);
          loadMoreButton.exclude();
          this.__showNoMessagesLabelIfNeeded(filter);
        });
    },

    __fetchMoreConversations: function() {
      if (this.__isFetchingMore) {
        return;
      }
      this.__isFetchingMore = true;
      this.__showLoadingSpinner(true);

      const filter = this.getCurrentFilter();
      const offset = this.__conversationListItems.length;
      osparc.store.ConversationsSupport.getInstance().fetchConversations(filter, offset)
        .then(resp => {
          if (resp && resp.conversations && resp.conversations.length) {
            resp.conversations.forEach(conversation => this.__addConversation(conversation));
          }
          this.__totalConversations = resp ? resp.total : null;
          this.__sortConversations();
          this.__updateBadgesVisibility(filter);
          this.__updateLoadingSpinner();
        })
        .finally(() => {
          this.__isFetchingMore = false;
        });
    },

    __onScroll: function() {
      if (!this.__hasMoreConversations()) {
        return;
      }
      const scroll = this.getChildControl("scroll-container");
      const pane = scroll.getChildControl("pane");
      const scrollTop = pane.getScrollY();
      const scrollHeight = pane.getScrollSize().height;
      const clientHeight = pane.getBounds() ? pane.getBounds().height : 0;
      if (scrollTop + clientHeight >= scrollHeight - 50) {
        this.__fetchMoreConversations();
      }
    },

    __hasMoreConversations: function() {
      if (this.__totalConversations === null) {
        return false;
      }
      return this.__conversationListItems.length < this.__totalConversations;
    },

    __updateLoadingSpinner: function() {
      this.__showLoadingSpinner(this.__hasMoreConversations());
    },

    __showLoadingSpinner: function(show) {
      const spinner = this.getChildControl("loading-spinner");
      const conversationsLayout = this.getChildControl("conversations-layout");
      if (show) {
        if (conversationsLayout.indexOf(spinner) === -1) {
          conversationsLayout.add(spinner);
        }
        spinner.show();
      } else {
        spinner.exclude();
      }
    },

    __listenToNewConversations: function() {
      osparc.store.ConversationsSupport.getInstance().addListener("conversationCreated", e => {
        const conversation = e.getData();
        this.__addConversation(conversation);
        this.__sortConversations();
        this.__applyCurrentFilter(this.getCurrentFilter());
        this.__fetchConversationCounts();
      });
    },

    __listenToConversationDeleted: function() {
      osparc.store.ConversationsSupport.getInstance().addListener("conversationDeleted", e => {
        const conversationId = e.getData()["conversationId"];
        this.__removeConversationPage(conversationId);
        this.__fetchConversationCounts();
      });
    },

    __addConversation: function(conversation) {
      // ignore it if it was already there
      const conversationId = conversation.getConversationId();
      const conversationItemFound = this.__getConversationItem(conversationId);
      if (conversationItemFound) {
        return null;
      }

      const conversationListItem = new osparc.support.ConversationListItem();
      conversationListItem.setConversation(conversation);
      conversationListItem.addListener("tap", () => this.fireDataEvent("openConversation", conversationId, this));
      conversation.addListener("changeLastMessageCreatedAt", () => this.__sortConversations(), this);
      const eventName = osparc.store.Groups.getInstance().amIASupportUser() ? "changeReadBySupport" : "changeReadByUser";
      conversation.addListener(eventName, () => {
        this.__applyCurrentFilter(this.getCurrentFilter());
        this.__fetchConversationCounts();
      }, this);
      conversation.addListener("changeArchived", () => {
        this.__applyCurrentFilter(this.getCurrentFilter());
        this.__fetchConversationCounts();
      }, this);
      this.__conversationListItems.push(conversationListItem);
      return conversationListItem;
    },

    __sortConversations: function() {
      const conversationsLayout = this.getChildControl("conversations-layout");
      conversationsLayout.removeAll();
      // sort them by modified date (newest first)
      this.__conversationListItems.sort((a, b) => {
        const aConversation = a.getConversation();
        const bConversation = b.getConversation();
        const aDate = aConversation.getLastMessageCreatedAt() || aConversation.getModified();
        const bDate = bConversation.getLastMessageCreatedAt() || bConversation.getModified();
        return bDate - aDate;
      });
      this.__conversationListItems.forEach(item => {
        if (item.getContentElement()) {
          conversationsLayout.add(item);
        }
      });
    },

    __removeConversationPage: function(conversationId) {
      const conversationItem = this.__getConversationItem(conversationId);
      if (conversationItem) {
        if (this.getChildControl("conversations-layout")) {
          this.getChildControl("conversations-layout").remove(conversationItem);
        }
        this.__conversationListItems = this.__conversationListItems.filter(item => item !== conversationItem);
      }
    },
  },
});
