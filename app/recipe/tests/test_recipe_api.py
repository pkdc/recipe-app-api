"""
Tests for recipe APIs.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe

from recipe.serializers import RecipeSerializer, RecipeDetailSerializer

RECIPES_URL = reverse('recipe:recipe-list')

def detail_url(recipe_id):
    """Create and return a recipe detail URL"""
    return reverse('recipe:recipe-detail', args=[recipe_id])

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
            'title': "Sample recipe",
            'time_minutes': 30,
            'price': Decimal('3.16'),
        }
        resp = self.client.post(RECIPES_URL, payload) # post to /api/recipe/recipes

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(id=resp.data['id'])
        for k, v in payload.items():
            self.assertEqual(v, getattr(recipe, k))
        self.assertEqual(recipe.user, self.user)

