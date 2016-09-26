describe('Accounts', () => {

  beforeEach( () => {
    browser.get('/accounts');
  });

  it('should have a list of accounts', () => {
    expect(element(by.css('account-list ul')).getText())
      .toEqual('Statement Account\nSavings\nCredit Card');
  });

  it('should show detail form on click', () => {
    element(by.css('account-list ul li:first-child')).click();

    expect(element(by.css('account-list account-detail')).isPresent());
    expect(element(by.css('account-list account-detail div h2')).getText())
      .toEqual('Statement Account');
  });

});
