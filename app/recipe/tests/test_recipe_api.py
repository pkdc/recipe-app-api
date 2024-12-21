"""
Tests for recipe APIs.
"""

from decimal import Decimal
import tempfile
import os

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    Recipe,
    Tag
)

from recipe.serializers import RecipeSerializer, RecipeDetailSerializer

RECIPES_URL = reverse('recipe:recipe-list')

def detail_url(recipe_id):
    """Create and return a recipe detail URL"""
    return reverse('recipe:recipe-detail', args=[recipe_id])

def image_upload_url(recipe_id):
    """Create and return an image upload URL"""
    return reverse('recipe:recipe-upload-image', args=[recipe_id])

def create_recipe(user, **params):
    """Create and return a sample recipe"""
    defaults = {
        'title': 'Sample recipe',
        'time_minutes': 16,
        'price': Decimal('3.16'),
        'description': 'Sample description',
        'link': 'http://example.com/recipe.pdf',
    }
    defaults.update(params)

    recipe = Recipe.objects.create(user=user, **defaults)
    return recipe

class PublicRecipeApiTests(TestCase):
    """Test unauthenticated recipe API request"""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test authentication is required to call API"""

        resp = self.client.get(RECIPES_URL)

        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

class PrivateRecipeApiTests(TestCase):
    """Test authenticated recipe API requests"""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            'user@example.com',
            'password123',
        )
        self.client.force_authenticate(self.user)

    def test_retrieve_recipes(self):
        """Test retrieving a list of recipes"""

        create_recipe(user=self.user)
        create_recipe(user=self.user)

        # Simulate a GET request and store the response
        resp = self.client.get(RECIPES_URL)

        # Get all recipes from db and serialize them
        recipes = Recipe.objects.all().order_by('-id')
        serializer = RecipeSerializer(recipes, many=True)

        # Assert the resp is the same as the serialized data from db
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, serializer.data)

    def test_recipes_limited_to_user(self):
        """Test list of recipes is limited to the authenticated user"""
        other_user = get_user_model().objects.create_user(
            'other@example.com',
            'password123',
        )
        create_recipe(user=other_user)
        create_recipe(user=self.user)

        # Simulate a GET request and store the response
        resp = self.client.get(RECIPES_URL)

        # Get all recipes of our auth user from db and serialize them
        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        # Assert the resp is the same as the serialized data from db
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, serializer.data)

    def test_view_recipe_detail(self):
        """Test get recipe detail"""
        recipe = create_recipe(user=self.user)

        # Simulate a GET request and store the response
        url = detail_url(recipe.id)
        resp = self.client.get(url)

        # Get recipe detail from db and serialize it
        serializer = RecipeDetailSerializer(recipe)

        # Assert the resp is the same as the serialized data from db
        self.assertEqual(resp.data, serializer.data)

    def test_create_recipe(self):
        """Test creating a recipe"""
        payload = {
            'title': "sample recipe",
            'time_minutes': 30,
            'price': Decimal('3.16'),
        }
        resp = self.client.post(RECIPES_URL, payload) # post to /api/recipe/recipes

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(id=resp.data['id'])
        for k, v in payload.items():
            self.assertEqual(v, getattr(recipe, k))
        self.assertEqual(recipe.user, self.user)

    def test_create_recipe_with_new_tags(self):
        """Test creating a recipe with new tags"""
        payload = {
            'title': 'thai curry',
            'time_minutes': 30,
            'price': Decimal('17.0'),
            'tags': [{'name': 'thai'}, {'name': 'dinner'}]
        }
        resp = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)
        for tag in payload['tags']:
            exists = recipe.tags.filter(name=tag['name']).exists()
            self.assertTrue(exists)

    def test_create_recipe_with_existing_tags(self):
        """Test creating a recipe with existing tags"""
        tag_indian = Tag.objects.create(user=self.user, name='indian')
        payload = {
            'title': 'Indian curry',
            'time_minutes': 36,
            'price': Decimal('31.6'),
            'tags': [{'name': 'indian'}, {'name': 'lunch'}]
        }
        resp = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2) # failed if 3
        self.assertIn(tag_indian, recipe.tags.all())
        for tag in payload['tags']:
            exists = recipe.tags.filter(user=self.user, name=tag['name']).exists()
            self.assertTrue(exists)

    def test_create_tag_on_update(self):
        """Test creating a tag when updating a recipe"""
        recipe = create_recipe(user=self.user)

        payload = {
            'tags': [{'name': 'lunch'}]
        }
        url = detail_url(recipe.id)
        resp = self.client.patch(url, payload, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        new_tag_from_db = Tag.objects.get(user= self.user, name='lunch')
        self.assertIn(new_tag_from_db, recipe.tags.all())

    def test_update_recipe_assign_tag(self):
        """Test assigning an existing tag when updating a recipe."""
        tag_breakfast = Tag.objects.create(user=self.user, name='breakfast')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag_breakfast)

        tag_lunch = Tag.objects.create(user=self.user, name='lunch')
        payload = {
            'tags': [{'name': 'lunch'}]
        }
        resp = self.client.patch(detail_url(recipe.id), payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # tag_lunch = Tag.objects.create(user=self.user, name='Lunch')
        # need to create a tag-lunch before sending the payload
        # coz wee are testing the update of EXISTING tags
        self.assertIn(tag_lunch, recipe.tags.all())
        self.assertNotIn(tag_breakfast, recipe.tags.all())

    def test_clear_recipe_tags(self):
        """Test clearing a recipes tags"""
        tag = Tag.objects.create(user=self.user, name='Dessert')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag)

        payload = {
            'tags': []
        }
        resp = self.client.patch(detail_url(recipe.id), payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.tags.count(), 0)
        # self.asssertNotIn(tag, recipe.tags.all())

    def test_filter_by_tags(self):
        """Test filtering recipes by tags"""
        r1 = create_recipe(user=self.user, title='Thai Vegan Curry')
        r2 = create_recipe(user=self.user, title='Aubergine Noodles')
        tag1 = Tag.objects.create(user=self.user, name='Vegan')
        tag2 = Tag.objects.create(user=self.user, name='Vegetarian')
        r1.tags.add(tag1)
        r2.tags.add(tag2)
        r3 = create_recipe(user=self.user, title='Fish and chips')

        params = {'tags': f'{tag1.id}, {tag2.id}'}
        resp = self.client.get(RECIPES_URL, params)

        s1 = RecipeSerializer(r1)
        s2 = RecipeSerializer(r2)
        s3 = RecipeSerializer(r3)
        self.assertIn(s1.data, resp.data)
        self.assertIn(s2.data, resp.data)
        self.assertNotIn(s3.data, resp.data)

class RecipeImageUploadTests(TestCase):
    """Tests for image upload API"""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            'user@example.com',
            'password123',
        )
        self.client.force_authenticate(self.user)
        self.recipe = create_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete()

    def test_upload_image_to_recipe(self):
        """Test uploading an image to a recipe"""
        url = image_upload_url(self.recipe.id)
        with tempfile.NamedTemporaryFile(suffix = '.jpg') as image_file:
            img = Image.new('RGB', (10, 10))
            img.save(image_file, format='JPEG')
            image_file.seek(0)
            payload = {
                'image': image_file,
            }
            resp = self.client.post(url, payload, format='multipart')
            self.recipe.refresh_from_db()

            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            self.assertIn('image', resp.data)
            self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_image_bad_request(self):
        """Test uploading an invalid image"""
        url = image_upload_url(self.recipe.id)
        payload = {'image': 'notanimage'}

        resp = self.client.post(url, payload, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
