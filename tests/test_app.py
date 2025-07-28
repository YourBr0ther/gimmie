import unittest
import json
from app import app
from models import db

class GimmieTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['LOGIN_PASSWORD'] = 'testpassword'
        self.app = app.test_client()
        
        with app.app_context():
            db.create_all()
    
    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()
    
    def login(self):
        return self.app.post('/login', data={'password': 'testpassword'}, follow_redirects=True)
    
    def test_login_required(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 302)
    
    def test_login(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Gimmie', response.data)
    
    def test_add_item(self):
        self.login()
        
        item_data = {
            'name': 'Test Item',
            'cost': 29.99,
            'link': 'https://example.com',
            'type': 'want'
        }
        
        response = self.app.post('/api/items',
                               data=json.dumps(item_data),
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'Test Item')
        self.assertEqual(data['position'], 1)
    
    def test_get_items(self):
        self.login()
        
        self.app.post('/api/items',
                     data=json.dumps({'name': 'Item 1', 'type': 'want'}),
                     content_type='application/json')
        
        self.app.post('/api/items',
                     data=json.dumps({'name': 'Item 2', 'type': 'need'}),
                     content_type='application/json')
        
        response = self.app.get('/api/items')
        data = json.loads(response.data)
        
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['name'], 'Item 1')
        self.assertEqual(data[1]['name'], 'Item 2')
    
    def test_move_item(self):
        self.login()
        
        response1 = self.app.post('/api/items',
                                data=json.dumps({'name': 'Item 1', 'type': 'want'}),
                                content_type='application/json')
        
        response2 = self.app.post('/api/items',
                                data=json.dumps({'name': 'Item 2', 'type': 'need'}),
                                content_type='application/json')
        
        item2_id = json.loads(response2.data)['id']
        
        self.app.post(f'/api/items/{item2_id}/move',
                     data=json.dumps({'direction': 'up'}),
                     content_type='application/json')
        
        response = self.app.get('/api/items')
        data = json.loads(response.data)
        
        self.assertEqual(data[0]['name'], 'Item 2')
        self.assertEqual(data[1]['name'], 'Item 1')

if __name__ == '__main__':
    unittest.main()