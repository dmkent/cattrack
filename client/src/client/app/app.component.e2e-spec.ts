describe('App', () => {

  beforeEach( () => {
    browser.get('/');
  });

  it('should have a title', () => {
    expect(browser.getTitle()).toEqual('CatTrack');
  });

  it('should have <nav>', () => {
    expect(element(by.css('sd-app nav')).isPresent()).toEqual(true);
  });

  it('should have correct nav text for Dashboard', () => {
    expect(element(by.css('sd-app nav div ul li:nth-child(1) a')).getText()).toEqual('Dashboard');
  });

  it('should have correct nav text for Transactions', () => {
    expect(element(by.css('sd-app nav div ul li:nth-child(2) a')).getText()).toEqual('Accounts');
  });

  it('should have correct nav text for Transactions', () => {
    expect(element(by.css('sd-app nav div ul li:nth-child(3) a')).getText()).toEqual('Transactions');
  });

});
