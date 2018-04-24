import numpy as np

from unittest.mock import patch

from django.test import override_settings

from experiment_groups.models import ExperimentGroupIteration
from experiment_groups.schemas import BOIterationConfig
from experiment_groups.search_managers import (
    BOSearchManager,
    GridSearchManager,
    HyperbandSearchManager,
    RandomSearchManager,
    get_search_algorithm_manager
)
from experiment_groups.search_managers.bayesian_optimization.optimizer import BOOptimizer
from experiment_groups.search_managers.bayesian_optimization.space import SearchSpace
from factories.factory_experiment_groups import ExperimentGroupFactory
from factories.fixtures import (
    experiment_group_spec_content_bo,
    experiment_group_spec_content_early_stopping,
    experiment_group_spec_content_hyperband
)
from polyaxon_schemas.matrix import MatrixConfig
from polyaxon_schemas.settings import SettingsConfig
from tests.utils import BaseTest


@override_settings(DEPLOY_RUNNER=False)
class TestIterationManagers(BaseTest):
    def test_get_search_iteration_manager(self):
        # Grid search
        experiment_group = ExperimentGroupFactory()
        assert isinstance(get_search_algorithm_manager(experiment_group.params_config),
                          GridSearchManager)

        # Random search
        experiment_group = ExperimentGroupFactory(
            content=experiment_group_spec_content_early_stopping)
        assert isinstance(get_search_algorithm_manager(experiment_group.params_config),
                          RandomSearchManager)

        # Hyperband
        experiment_group = ExperimentGroupFactory(
            content=experiment_group_spec_content_hyperband)
        assert isinstance(get_search_algorithm_manager(experiment_group.params_config),
                          HyperbandSearchManager)

        # BO
        experiment_group = ExperimentGroupFactory(
            content=experiment_group_spec_content_bo)
        assert isinstance(get_search_algorithm_manager(experiment_group.params_config),
                          BOSearchManager)


@override_settings(DEPLOY_RUNNER=False)
class TestGridSearchManager(BaseTest):
    def test_get_suggestions(self):
        params_config = SettingsConfig.from_dict({
            'concurrency': 2,
            'grid_search': {'n_experiments': 10},
            'matrix': {'feature': {'values': [1, 2, 3]}}
        })
        manager = GridSearchManager(params_config=params_config)
        assert len(manager.get_suggestions()) == 3

        params_config = SettingsConfig.from_dict({
            'concurrency': 2,
            'grid_search': {'n_experiments': 10},
            'matrix': {
                'feature1': {'values': [1, 2, 3]},
                'feature2': {'linspace': [1, 2, 5]},
                'feature3': {'range': [1, 5, 1]}
            }
        })
        manager = GridSearchManager(params_config=params_config)
        assert len(manager.get_suggestions()) == 10

    def test_get_suggestions_calls_to_numpy(self):
        params_config = SettingsConfig.from_dict({
            'concurrency': 2,
            'grid_search': {'n_experiments': 10},
            'matrix': {'feature': {'values': [1, 2, 3]}}
        })
        manager = GridSearchManager(params_config=params_config)
        with patch.object(MatrixConfig, 'to_numpy') as to_numpy_mock:
            manager.get_suggestions()

        assert to_numpy_mock.call_count == 1

        params_config = SettingsConfig.from_dict({
            'concurrency': 2,
            'grid_search': {'n_experiments': 10},
            'matrix': {
                'feature1': {'values': [1, 2, 3]},
                'feature2': {'logspace': '0.01:0.1:5'}
            }
        })
        manager = GridSearchManager(params_config=params_config)
        with patch.object(MatrixConfig, 'to_numpy') as to_numpy_mock:
            manager.get_suggestions()

        assert to_numpy_mock.call_count == 2


@override_settings(DEPLOY_RUNNER=False)
class TestRandomSearchManager(BaseTest):
    def test_get_suggestions(self):
        params_config = SettingsConfig.from_dict({
            'concurrency': 2,
            'random_search': {'n_experiments': 10},
            'matrix': {
                'feature1': {'values': [1, 2, 3]},
                'feature2': {'linspace': [1, 2, 5]},
                'feature3': {'range': [1, 5, 1]}
            }
        })
        manager = RandomSearchManager(params_config=params_config)
        assert len(manager.get_suggestions()) == 10

        params_config = SettingsConfig.from_dict({
            'concurrency': 2,
            'random_search': {'n_experiments': 10},
            'matrix': {
                'feature1': {'pvalues': [(1, 0.3), (2, 0.3), (3, 0.3)]},
                'feature2': {'uniform': [0, 1]},
                'feature3': {'qlognormal': [0, 0.5, 0.51]}
            }
        })
        manager = RandomSearchManager(params_config=params_config)
        assert len(manager.get_suggestions()) == 10

    def test_get_suggestions_calls_sample(self):
        params_config = SettingsConfig.from_dict({
            'concurrency': 2,
            'random_search': {'n_experiments': 1},
            'matrix': {
                'feature1': {'values': [1, 2, 3]},
                'feature2': {'linspace': [1, 2, 5]},
                'feature3': {'range': [1, 5, 1]}
            }
        })
        manager = RandomSearchManager(params_config=params_config)
        with patch.object(MatrixConfig, 'sample') as sample_mock:
            manager.get_suggestions()

        assert sample_mock.call_count == 3

        params_config = SettingsConfig.from_dict({
            'concurrency': 2,
            'random_search': {'n_experiments': 1},
            'matrix': {
                'feature1': {'pvalues': [(1, 0.3), (2, 0.3), (3, 0.3)]},
                'feature2': {'uniform': [0, 1]},
                'feature3': {'qlognormal': [0, 0.5, 0.51]},
                'feature4': {'range': [1, 5, 1]}
            }
        })
        manager = RandomSearchManager(params_config=params_config)
        with patch.object(MatrixConfig, 'sample') as sample_mock:
            manager.get_suggestions()

        assert sample_mock.call_count == 4


@override_settings(DEPLOY_RUNNER=False)
class TestHyperbandSearchManager(BaseTest):
    def setUp(self):
        params_config = SettingsConfig.from_dict({
            'concurrency': 2,
            'hyperband': {
                'max_iter': 10,
                'eta': 3,
                'resource': {'name': 'steps', 'type': 'float'},
                'resume': False,
                'metric': {'name': 'loss', 'optimization': 'minimize'}
            },
            'matrix': {
                'feature1': {'values': [1, 2, 3]},
                'feature2': {'linspace': [1, 2, 5]},
                'feature3': {'range': [1, 5, 1]}
            }
        })
        self.manager1 = HyperbandSearchManager(params_config=params_config)

        params_config = SettingsConfig.from_dict({
            'concurrency': 2,
            'hyperband': {
                'max_iter': 81,
                'eta': 3,
                'resource': {'name': 'size', 'type': 'int'},
                'resume': False,
                'metric': {'name': 'loss', 'optimization': 'minimize'}
            },
            'matrix': {
                'feature1': {'values': [1, 2, 3]},
                'feature2': {'linspace': [1, 2, 5]},
                'feature3': {'range': [1, 5, 1]},
                'feature4': {'range': [1, 5, 1]}
            }
        })
        self.manager2 = HyperbandSearchManager(params_config=params_config)

    @staticmethod
    def almost_equal(value, value_compare):
        assert value_compare - 0.02 <= value <= value_compare + 0.02

    def test_hyperband_properties(self):
        # Manager1
        assert self.manager1.max_iter == 10
        assert self.manager1.eta == 3
        assert self.manager1.s_max == 2
        assert self.manager1.B == (self.manager1.s_max + 1) * self.manager1.max_iter

        assert self.manager2.max_iter == 81
        assert self.manager2.eta == 3
        assert self.manager2.s_max == 4
        assert self.manager2.B == (self.manager2.s_max + 1) * self.manager2.max_iter

    def test_get_bracket(self):
        # Manager1
        assert self.manager1.get_bracket(iteration=0) == 2
        assert self.manager1.get_bracket(iteration=1) == 1
        assert self.manager1.get_bracket(iteration=2) == 0

        # Manager2
        assert self.manager2.get_bracket(iteration=0) == 4
        assert self.manager2.get_bracket(iteration=1) == 3
        assert self.manager2.get_bracket(iteration=2) == 2
        assert self.manager2.get_bracket(iteration=3) == 1
        assert self.manager2.get_bracket(iteration=4) == 0

    def test_get_n_configs(self):
        # Manager1
        assert self.manager1.get_n_configs(bracket=2) == 9
        assert self.manager1.get_n_configs(bracket=1) == 5
        assert self.manager1.get_n_configs(bracket=0) == 3

        # Manager2
        assert self.manager2.get_n_configs(bracket=4) == 81
        assert self.manager2.get_n_configs(bracket=3) == 34
        assert self.manager2.get_n_configs(bracket=2) == 15
        assert self.manager2.get_n_configs(bracket=1) == 8
        assert self.manager2.get_n_configs(bracket=0) == 5

    def test_get_n_configs_to_keep(self):
        # Number of config to keep [/n_suggestions, /iteration]

        # Manager1
        # Iteration == 0
        assert self.manager1.get_n_config_to_keep(n_suggestions=9, bracket_iteration=0) == 3
        assert self.manager1.get_n_config_to_keep(n_suggestions=9, bracket_iteration=1) == 1
        assert self.manager1.get_n_config_to_keep(n_suggestions=9, bracket_iteration=2) == 0

        assert self.manager1.get_n_config_to_keep_for_iteration(iteration=0,
                                                                bracket_iteration=0) == 3
        assert self.manager1.get_n_config_to_keep_for_iteration(iteration=0,
                                                                bracket_iteration=1) == 1
        assert self.manager1.get_n_config_to_keep_for_iteration(iteration=0,
                                                                bracket_iteration=2) == 0

        # Iteration == 1
        assert self.manager1.get_n_config_to_keep(n_suggestions=5, bracket_iteration=0) == 1
        assert self.manager1.get_n_config_to_keep(n_suggestions=5, bracket_iteration=1) == 0

        assert self.manager1.get_n_config_to_keep_for_iteration(iteration=1,
                                                                bracket_iteration=0) == 1
        assert self.manager1.get_n_config_to_keep_for_iteration(iteration=1,
                                                                bracket_iteration=1) == 0

        # Iteration == 2
        assert self.manager1.get_n_config_to_keep(n_suggestions=3, bracket_iteration=0) == 1
        assert self.manager1.get_n_config_to_keep_for_iteration(iteration=2,
                                                                bracket_iteration=0) == 1

        # Manager2
        # Iteration == 0
        assert self.manager2.get_n_config_to_keep(n_suggestions=81,
                                                  bracket_iteration=0) == 27
        assert self.manager2.get_n_config_to_keep(n_suggestions=81,
                                                  bracket_iteration=1) == 9
        assert self.manager2.get_n_config_to_keep(n_suggestions=81,
                                                  bracket_iteration=2) == 3
        assert self.manager2.get_n_config_to_keep(n_suggestions=81,
                                                  bracket_iteration=3) == 1
        assert self.manager2.get_n_config_to_keep(n_suggestions=81,
                                                  bracket_iteration=4) == 0

        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=0,
                                                                bracket_iteration=0) == 27
        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=0,
                                                                bracket_iteration=1) == 9
        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=0,
                                                                bracket_iteration=2) == 3
        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=0,
                                                                bracket_iteration=3) == 1
        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=0,
                                                                bracket_iteration=4) == 0

        # Iteration == 1
        assert self.manager2.get_n_config_to_keep(n_suggestions=34, bracket_iteration=0) == 11
        assert self.manager2.get_n_config_to_keep(n_suggestions=34, bracket_iteration=1) == 3
        assert self.manager2.get_n_config_to_keep(n_suggestions=34, bracket_iteration=2) == 1
        assert self.manager2.get_n_config_to_keep(n_suggestions=34, bracket_iteration=3) == 0

        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=1,
                                                                bracket_iteration=0) == 11
        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=1,
                                                                bracket_iteration=1) == 3
        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=1,
                                                                bracket_iteration=2) == 1
        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=1,
                                                                bracket_iteration=3) == 0

        # Iteration == 2
        assert self.manager2.get_n_config_to_keep(n_suggestions=15, bracket_iteration=0) == 5
        assert self.manager2.get_n_config_to_keep(n_suggestions=15, bracket_iteration=1) == 1
        assert self.manager2.get_n_config_to_keep(n_suggestions=15, bracket_iteration=2) == 0

        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=2,
                                                                bracket_iteration=0) == 5
        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=2,
                                                                bracket_iteration=1) == 1
        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=2,
                                                                bracket_iteration=2) == 0

        # Iteration == 3
        assert self.manager2.get_n_config_to_keep(n_suggestions=8, bracket_iteration=0) == 2
        assert self.manager2.get_n_config_to_keep(n_suggestions=8, bracket_iteration=1) == 0

        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=3,
                                                                bracket_iteration=0) == 2
        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=3,
                                                                bracket_iteration=1) == 0

        # Iteration == 4
        assert self.manager2.get_n_config_to_keep(n_suggestions=5, bracket_iteration=0) == 1

        assert self.manager2.get_n_config_to_keep_for_iteration(iteration=4,
                                                                bracket_iteration=0) == 1

    def test_get_resources(self):
        # Number of resources [/bracket, /iteration]

        # Manager1
        self.almost_equal(self.manager1.get_resources(bracket=2), 1.11)
        self.almost_equal(self.manager1.get_resources(bracket=1), 3.33)
        self.almost_equal(self.manager1.get_resources(bracket=0), 10)

        self.almost_equal(self.manager1.get_resources_for_iteration(iteration=0), 1.11)
        self.almost_equal(self.manager1.get_resources_for_iteration(iteration=1), 3.33)
        self.almost_equal(self.manager1.get_resources_for_iteration(iteration=2), 10)

        # Manager2
        self.almost_equal(self.manager2.get_resources(bracket=4), 1)
        self.almost_equal(self.manager2.get_resources(bracket=3), 3)
        self.almost_equal(self.manager2.get_resources(bracket=2), 9)
        self.almost_equal(self.manager2.get_resources(bracket=1), 27)
        self.almost_equal(self.manager2.get_resources(bracket=0), 81)

        self.almost_equal(self.manager2.get_resources_for_iteration(iteration=0), 1)
        self.almost_equal(self.manager2.get_resources_for_iteration(iteration=1), 3)
        self.almost_equal(self.manager2.get_resources_for_iteration(iteration=2), 9)
        self.almost_equal(self.manager2.get_resources_for_iteration(iteration=3), 27)
        self.almost_equal(self.manager2.get_resources_for_iteration(iteration=4), 81)

    def test_get_n_resources(self):
        # Number of iteration resources

        # Manager1
        # Iteration == 0
        self.almost_equal(
            self.manager1.get_n_resources(n_resources=1.11, bracket_iteration=0), 1.11)
        self.almost_equal(
            self.manager1.get_n_resources(n_resources=1.11, bracket_iteration=1), 3.33)
        self.almost_equal(
            self.manager1.get_n_resources(n_resources=1.11, bracket_iteration=2), 9.99)

        self.almost_equal(
            self.manager1.get_n_resources_for_iteration(iteration=0, bracket_iteration=0), 1.11)
        self.almost_equal(
            self.manager1.get_n_resources_for_iteration(iteration=0, bracket_iteration=1), 3.33)
        self.almost_equal(
            self.manager1.get_n_resources_for_iteration(iteration=0, bracket_iteration=2), 9.99)

        # Iteration == 1
        self.almost_equal(
            self.manager1.get_n_resources(n_resources=3.33, bracket_iteration=0), 3.33)
        self.almost_equal(
            self.manager1.get_n_resources(n_resources=3.33, bracket_iteration=1), 9.99)

        self.almost_equal(
            self.manager1.get_n_resources_for_iteration(iteration=1, bracket_iteration=0), 3.33)
        self.almost_equal(
            self.manager1.get_n_resources_for_iteration(iteration=1, bracket_iteration=1), 9.99)

        # Iteration == 2
        self.almost_equal(
            self.manager1.get_n_resources(n_resources=9.99, bracket_iteration=0), 9.99)

        self.almost_equal(
            self.manager1.get_n_resources_for_iteration(iteration=2, bracket_iteration=0), 9.99)

        # Manager2
        # Iteration == 0
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=1, bracket_iteration=0), 1)
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=1, bracket_iteration=1), 3)
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=1, bracket_iteration=2), 9)
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=1, bracket_iteration=3), 27)
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=1, bracket_iteration=4), 81)

        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=0, bracket_iteration=0), 1)
        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=0, bracket_iteration=1), 3)
        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=0, bracket_iteration=2), 9)
        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=0, bracket_iteration=3), 27)
        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=0, bracket_iteration=4), 81)

        # Iteration == 1
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=3, bracket_iteration=0), 3)
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=3, bracket_iteration=1), 9)
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=3, bracket_iteration=2), 27)
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=3, bracket_iteration=3), 81)

        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=1, bracket_iteration=0), 3)
        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=1, bracket_iteration=1), 9)
        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=1, bracket_iteration=2), 27)
        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=1, bracket_iteration=3), 81)

        # Iteration == 2
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=9, bracket_iteration=0), 9)
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=9, bracket_iteration=1), 27)
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=9, bracket_iteration=2), 81)

        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=2, bracket_iteration=0), 9)
        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=2, bracket_iteration=1), 27)
        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=2, bracket_iteration=2), 81)

        # Iteration == 3
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=27, bracket_iteration=0), 27)
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=27, bracket_iteration=1), 81)

        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=3, bracket_iteration=0), 27)
        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=3, bracket_iteration=1), 81)

        # Iteration == 4
        self.almost_equal(
            self.manager2.get_n_resources(n_resources=81, bracket_iteration=0), 81)

        self.almost_equal(
            self.manager2.get_n_resources_for_iteration(iteration=4, bracket_iteration=0), 81)

    def test_should_reschedule(self):
        assert self.manager1.should_reschedule(iteration=0, bracket_iteration=0) is False
        assert self.manager1.should_reschedule(iteration=0, bracket_iteration=1) is False
        assert self.manager1.should_reschedule(iteration=0, bracket_iteration=2) is True
        assert self.manager1.should_reschedule(iteration=0, bracket_iteration=3) is True
        assert self.manager1.should_reschedule(iteration=1, bracket_iteration=0) is False
        assert self.manager1.should_reschedule(iteration=1, bracket_iteration=1) is True
        assert self.manager1.should_reschedule(iteration=1, bracket_iteration=2) is True
        assert self.manager1.should_reschedule(iteration=2, bracket_iteration=0) is False
        assert self.manager1.should_reschedule(iteration=2, bracket_iteration=1) is False
        assert self.manager1.should_reschedule(iteration=5, bracket_iteration=0) is False

    def test_should_reduce_configs(self):
        assert self.manager1.should_reduce_configs(iteration=0, bracket_iteration=0) is True
        assert self.manager1.should_reduce_configs(iteration=0, bracket_iteration=1) is True
        assert self.manager1.should_reduce_configs(iteration=0, bracket_iteration=2) is False
        assert self.manager1.should_reduce_configs(iteration=0, bracket_iteration=3) is False
        assert self.manager1.should_reduce_configs(iteration=1, bracket_iteration=0) is True
        assert self.manager1.should_reduce_configs(iteration=1, bracket_iteration=1) is False
        assert self.manager1.should_reduce_configs(iteration=1, bracket_iteration=2) is False
        assert self.manager1.should_reduce_configs(iteration=2, bracket_iteration=0) is True
        assert self.manager1.should_reduce_configs(iteration=2, bracket_iteration=1) is False
        assert self.manager1.should_reduce_configs(iteration=5, bracket_iteration=0) is False

    def test_get_suggestions_raises_for_wrong_iterations(self):
        with self.assertRaises(ValueError):
            self.manager1.get_suggestions()

        with self.assertRaises(ValueError):
            self.manager1.get_suggestions(1)

    def test_get_suggestions(self):
        # Manager1
        experiment_group = ExperimentGroupFactory(
            params=self.manager1.params_config.to_dict()
        )
        # Fake iteration
        ExperimentGroupIteration.objects.create(
            experiment_group=experiment_group,
            data={
                'iteration': 0,
                'bracket_iteration': 2
            })
        suggestions = self.manager1.get_suggestions(
            iteration_config=experiment_group.iteration_config)

        assert len(suggestions) == 9
        for suggestion in suggestions:
            assert 'steps' in suggestion
            self.almost_equal(suggestion['steps'], 9.99)
            assert 'feature1' in suggestion
            assert 'feature2' in suggestion
            assert 'feature3' in suggestion

        # Fake iteration
        ExperimentGroupIteration.objects.create(
            experiment_group=experiment_group,
            data={
                'iteration': 1,
                'bracket_iteration': 0
            })
        suggestions = self.manager1.get_suggestions(
            iteration_config=experiment_group.iteration_config)
        assert len(suggestions) == 5
        for suggestion in suggestions:
            assert 'steps' in suggestion
            self.almost_equal(suggestion['steps'], 3.33)
            assert 'feature1' in suggestion
            assert 'feature2' in suggestion
            assert 'feature3' in suggestion

        # Fake iteration
        ExperimentGroupIteration.objects.create(
            experiment_group=experiment_group,
            data={
                'iteration': 2,
                'bracket_iteration': 0
            })
        suggestions = self.manager1.get_suggestions(
            iteration_config=experiment_group.iteration_config)
        assert len(suggestions) == 3
        for suggestion in suggestions:
            assert 'steps' in suggestion
            self.almost_equal(suggestion['steps'], 9.99)
            assert 'feature1' in suggestion
            assert 'feature2' in suggestion
            assert 'feature3' in suggestion

        # Manager2
        experiment_group = ExperimentGroupFactory(
            params=self.manager2.params_config.to_dict()
        )

        # Fake iteration
        ExperimentGroupIteration.objects.create(
            experiment_group=experiment_group,
            data={
                'iteration': 2,
                'bracket_iteration': 0
            })
        suggestions = self.manager2.get_suggestions(
            iteration_config=experiment_group.iteration_config)
        assert len(suggestions) == 15
        for suggestion in suggestions:
            assert 'size' in suggestion
            self.almost_equal(suggestion['size'], 9)
            assert 'feature1' in suggestion
            assert 'feature2' in suggestion
            assert 'feature3' in suggestion
            assert 'feature4' in suggestion

        # Fake iteration
        ExperimentGroupIteration.objects.create(
            experiment_group=experiment_group,
            data={
                'iteration': 4,
                'bracket_iteration': 0
            })
        suggestions = self.manager2.get_suggestions(
            iteration_config=experiment_group.iteration_config)
        assert len(suggestions) == 5
        for suggestion in suggestions:
            assert 'size' in suggestion
            self.almost_equal(suggestion['size'], 81)
            assert 'feature1' in suggestion
            assert 'feature2' in suggestion
            assert 'feature3' in suggestion
            assert 'feature4' in suggestion


@override_settings(DEPLOY_RUNNER=False)
class TestBOSearchManager(BaseTest):
    def setUp(self):
        params_config = SettingsConfig.from_dict({
            'concurrency': 2,
            'bo': {
                'n_iterations': 5,
                'n_initial_trials': 5,
                'metric': {
                    'name': 'loss',
                    'optimization': 'minimize'
                },
                'utility_function': {
                    'acquisition_function': 'ucb',
                    'kappa': 1.2,
                    'gaussian_process': {
                        'kernel': 'matern',
                        'length_scale': 1.0,
                        'nu': 1.9,
                        'n_restarts_optimizer': 0
                    }
                }
            },
            'matrix': {
                'feature1': {'values': [1, 2, 3]},
                'feature2': {'linspace': [1, 2, 5]},
                'feature3': {'range': [1, 5, 1]}
            }
        })
        self.manager1 = BOSearchManager(params_config=params_config)

        params_config = SettingsConfig.from_dict({
            'concurrency': 2,
            'bo': {
                'n_iterations': 4,
                'n_initial_trials': 4,
                'metric': {
                    'name': 'accuracy',
                    'optimization': 'maximize'
                },
                'utility_function': {
                    'acquisition_function': 'ei',
                    'eps': 1.2,
                    'gaussian_process': {
                        'kernel': 'matern',
                        'length_scale': 1.0,
                        'nu': 1.9,
                        'n_restarts_optimizer': 0
                    }
                }
            },
            'matrix': {
                'feature1': {'values': [1, 2, 3, 4, 5]},
                'feature2': {'linspace': [1, 5, 5]},
                'feature3': {'range': [1, 6, 1]},
                'feature4': {'uniform': [1, 5]},
                'feature5': {'values': ['a', 'b', 'c']},
            }
        })
        self.manager2 = BOSearchManager(params_config=params_config)

    def test_first_get_suggestions_returns_initial_random_suggestion(self):
        assert len(self.manager1.get_suggestions()) == 5
        assert len(self.manager2.get_suggestions()) == 4

    def test_iteration_suggestions_calls_optimizer(self):
        iteration_config = BOIterationConfig.from_dict({
            'iteration': 2,
            'old_experiment_ids': [1, 2, 3],
            'old_experiments_configs': [[1, {'feature1': 1, 'feature2': 1, 'feature3': 1}],
                                        [2, {'feature1': 2, 'feature2': 1.2, 'feature3': 2}],
                                        [3, {'feature1': 3, 'feature2': 1.3, 'feature3': 3}]],
            'old_experiments_metrics': [[1, 1], [2, 2], [3, 3]],
            'experiment_ids': [4],
            'experiments_configs': [[4, {'feature1': 2, 'feature2': 1.5, 'feature3': 4}]],
            'experiments_metrics': [[4, 4]]
        })
        with patch.object(BOOptimizer, 'get_suggestion') as get_suggestion_mock:
            self.manager1.get_suggestions(iteration_config)

        assert get_suggestion_mock.call_count == 1

    def test_space_search(self):
        # Space 1
        space1 = SearchSpace(params_config=self.manager1.params_config)

        assert space1.dim == 3
        assert len(space1.bounds) == 3
        assert len(space1.discrete_features) == 3
        assert len(space1.categorical_features) == 0

        for i, feature in enumerate(space1.features):
            # Bounds
            if feature == 'feature1':
                assert np.all(space1.bounds[i] == [1, 3])
            elif feature == 'feature2':
                assert np.all(space1.bounds[i] == [1, 2])
            elif feature == 'feature3':
                assert np.all(space1.bounds[i] == [1, 5])

        for feature in space1.features:
            # Features
            if feature == 'feature1':
                assert np.all(space1.discrete_features['feature1']['values'] == [1, 2, 3])
            elif feature == 'feature2':
                assert np.all(
                    space1.discrete_features['feature2']['values'] ==
                    np.asarray([1., 1.25, 1.5, 1.75, 2.]))
            elif feature == 'feature3':
                assert np.all(
                    space1.discrete_features['feature3']['values'] ==
                    np.asarray([1, 2, 3, 4]))

        # Space 2
        space2 = SearchSpace(params_config=self.manager2.params_config)

        assert space2.dim == 7
        assert len(space2.bounds) == 7
        assert len(space2.discrete_features) == 3
        assert len(space2.categorical_features) == 1
        assert len(space2.features) == 5

        for i, feature in enumerate(space2.features):
            # Bounds
            if feature == 'feature1':
                assert np.all(space2.bounds[i] == [1, 5])
            elif feature == 'feature2':
                assert np.all(space2.bounds[i] == [1, 5])
            elif feature == 'feature3':
                assert np.all(space2.bounds[i] == [1, 6])
            elif feature == 'feature4':
                assert np.all(space2.bounds[i] == [1, 5])
            elif feature == 'feature5':
                assert np.all(space2.bounds[i] == [0, 1])

        # One feature left is continuous

        # One categorical Features
        assert space2.categorical_features == {
            'feature5': {'values': ['a', 'b', 'c'], 'number': 3}
        }

        # 3 discrete Features
        assert space2.discrete_features['feature1']['values'] == [1, 2, 3, 4, 5]
        assert np.all(
            space2.discrete_features['feature2']['values'] ==
            np.asarray([1, 2, 3, 4, 5]))
        assert np.all(
            space2.discrete_features['feature3']['values'] ==
            np.asarray([1, 2, 3, 4, 5]))

    def test_add_observation_to_space_search(self):
        space1 = SearchSpace(params_config=self.manager1.params_config)

        assert space1.x == []
        assert space1.y == []

        configs = [
            {'feature1': 1, 'feature2': 1, 'feature3': 1},
            {'feature1': 2, 'feature2': 1.2, 'feature3': 2},
            {'feature1': 3, 'feature2': 1.3, 'feature3': 3}
        ]
        metrics = [1, 2, 3]

        space1.add_observations(
            configs=configs,
            metrics=metrics
        )

        assert len(space1.x) == 3
        assert len(space1.y) == 3

        for i, feature in enumerate(space1.features):
            if feature == 'feature1':
                assert np.all(space1.x[:, i] == [1, 2, 3])
            elif feature == 'feature2':
                assert np.all(space1.x[:, i] == [1, 1.2, 1.3])
            elif feature == 'feature3':
                assert np.all(space1.x[:, i] == [1, 2, 3])

        assert np.all(space1.y == np.array([-1, -2, -3]))

        space2 = SearchSpace(params_config=self.manager2.params_config)

        configs = [
            {'feature1': 1, 'feature2': 1, 'feature3': 1, 'feature4': 1, 'feature5': 'a'},
            {'feature1': 2, 'feature2': 1.2, 'feature3': 2, 'feature4': 4, 'feature5': 'b'},
            {'feature1': 3, 'feature2': 1.3, 'feature3': 3, 'feature4': 3, 'feature5': 'a'}
        ]
        metrics = [1, 2, 3]

        space2.add_observations(
            configs=configs,
            metrics=metrics
        )

        assert len(space2.x) == 3
        assert len(space2.y) == 3

        for i, feature in enumerate(space2.features):
            if feature == 'feature1':
                assert np.all(space2.x[:, i] == [1, 2, 3])
            elif feature == 'feature2':
                assert np.all(space2.x[:, i] == [1, 1.2, 1.3])
            elif feature == 'feature3':
                assert np.all(space2.x[:, i] == [1, 2, 3])
            elif feature == 'feature4':
                assert np.all(space2.x[:, i] == [1, 4, 3])
            elif feature == 'feature5':
                assert np.all(space2.x[:, i:i + 3] == [[1, 0, 0], [0, 1, 0], [1, 0, 0]])

        assert np.all(space2.y == np.array(metrics))

    def test_space_get_suggestion(self):
        space1 = SearchSpace(params_config=self.manager1.params_config)

        suggestion = space1.get_suggestion(suggestion=[1, 1, 1])
        assert suggestion == {'feature1': 1, 'feature2': 1, 'feature3': 1}

        suggestion = space1.get_suggestion(suggestion=[1, 1.2, 2])
        assert suggestion == {'feature1': 1, 'feature2': 1.25, 'feature3': 2}

        suggestion = space1.get_suggestion(suggestion=[1, 1.5, 3])
        assert suggestion == {'feature1': 1, 'feature2': 1.5, 'feature3': 3}

        space2 = SearchSpace(params_config=self.manager2.params_config)

        suggestion = space2.get_suggestion(suggestion=[1, 1, 1, 1, 1, 0, 0])
        assert suggestion == {'feature1': 1,
                              'feature2': 1,
                              'feature3': 1,
                              'feature4': 1,
                              'feature5': 'a'}

        suggestion = space2.get_suggestion(suggestion=[1, 1.2, 2, 3, 0, 0, 1])
        assert suggestion == {'feature1': 1,
                              'feature2': 1,
                              'feature3': 2,
                              'feature4': 3,
                              'feature5': 'c'}

        suggestion = space2.get_suggestion(suggestion=[1, 1.8, 3, 3, 0, 1, 0])
        assert suggestion == {'feature1': 1,
                              'feature2': 2,
                              'feature3': 3,
                              'feature4': 3,
                              'feature5': 'b'}
